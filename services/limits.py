"""
Tier-aware quota helpers — AI insights (daily), frontend challenges (monthly + bonus),
and streak freezes (monthly allowance).

Free tier:
  - 3 AI insights / day
  - 3 unique frontend challenges / month, +3 bonus after solving the first 3
  - 2 streak freezes / month
  - 1 company problem / day (handled separately in routes/companies.py)

Plus tier:
  - Unlimited AI insights, frontend challenges, company problems
  - 5 streak freezes / month
"""

import json
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from db import get_db


# ─── Period helpers ───────────────────────────────────────────────────────────

def today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


# ─── User tier lookup ─────────────────────────────────────────────────────────

def get_tier(username: str) -> str:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT tier FROM users WHERE username = ?", [username.lower()]
        ).fetchone()
        return (row["tier"] if row and row["tier"] else "free")
    finally:
        conn.close()


# ─── AI insights — daily counter ──────────────────────────────────────────────

AI_FREE_DAILY_LIMIT = 3


def check_ai_quota(username: str) -> Tuple[bool, Optional[int]]:
    """Return (allowed, remaining). remaining is None for plus (unlimited)."""
    tier = get_tier(username)
    if tier == "plus":
        return True, None

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT count FROM ai_usage WHERE username = ? AND date = ?",
            [username.lower(), today_str()],
        ).fetchone()
        used = (row["count"] if row else 0) or 0
        remaining = max(AI_FREE_DAILY_LIMIT - used, 0)
        return remaining > 0, remaining
    finally:
        conn.close()


def record_ai_use(username: str) -> None:
    """Increment today's counter. Plus users still get logged for analytics."""
    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO ai_usage (username, date, count)
            VALUES (?, ?, 1)
            ON CONFLICT(username, date) DO UPDATE SET count = count + 1
            """,
            [username.lower(), today_str()],
        )
        conn.commit()
    finally:
        conn.close()


# ─── Frontend challenges — monthly access + bonus ─────────────────────────────

FRONTEND_FREE_BASE = 3
FRONTEND_FREE_BONUS = 3  # unlocked after solving the base 3


def _get_frontend_usage(conn, username: str, period: str) -> Dict:
    row = conn.execute(
        "SELECT accessed_ids, bonus_unlocked FROM frontend_usage WHERE username = ? AND period_month = ?",
        [username, period],
    ).fetchone()
    if not row:
        return {"accessed_ids": [], "bonus_unlocked": False}
    try:
        ids = json.loads(row["accessed_ids"] or "[]")
    except Exception:
        ids = []
    return {"accessed_ids": ids, "bonus_unlocked": bool(row["bonus_unlocked"])}


def frontend_status(username: str) -> Dict:
    """Return monthly frontend access status. Plus tier is unlimited."""
    tier = get_tier(username)
    if tier == "plus":
        return {
            "tier": "plus",
            "unlimited": True,
            "accessed_ids": [],
            "cap": None,
            "bonus_unlocked": True,
            "remaining": None,
        }

    conn = get_db()
    try:
        usage = _get_frontend_usage(conn, username.lower(), current_month())
        cap = FRONTEND_FREE_BASE + (FRONTEND_FREE_BONUS if usage["bonus_unlocked"] else 0)
        return {
            "tier": "free",
            "unlimited": False,
            "accessed_ids": usage["accessed_ids"],
            "cap": cap,
            "bonus_unlocked": usage["bonus_unlocked"],
            "remaining": max(cap - len(usage["accessed_ids"]), 0),
        }
    finally:
        conn.close()


def can_access_frontend(username: str, challenge_id: str) -> Tuple[bool, str]:
    """Check + register access for a free user. Plus is always allowed.

    Returns (allowed, reason). On a successful first-time access for a free
    user, this records the challenge_id under their monthly bucket.
    """
    tier = get_tier(username)
    if tier == "plus":
        return True, "plus"

    period = current_month()
    norm_user = username.lower()

    conn = get_db()
    try:
        usage = _get_frontend_usage(conn, norm_user, period)
        ids = usage["accessed_ids"]
        cap = FRONTEND_FREE_BASE + (FRONTEND_FREE_BONUS if usage["bonus_unlocked"] else 0)

        # Already accessed this month — always allowed.
        if challenge_id in ids:
            return True, "already_accessed"

        # New access — check cap.
        if len(ids) >= cap:
            return False, "monthly_cap_reached"

        ids.append(challenge_id)
        conn.execute(
            """
            INSERT INTO frontend_usage (username, period_month, accessed_ids, bonus_unlocked)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(username, period_month) DO UPDATE SET accessed_ids = excluded.accessed_ids
            """,
            [norm_user, period, json.dumps(ids), 1 if usage["bonus_unlocked"] else 0],
        )
        conn.commit()
        return True, "newly_accessed"
    finally:
        conn.close()


def maybe_unlock_frontend_bonus(username: str) -> bool:
    """If a free user has solved 3+ unique challenges this month, flip bonus_unlocked.

    Called after a successful first-solve. Returns True if bonus was just unlocked.
    """
    tier = get_tier(username)
    if tier == "plus":
        return False

    period = current_month()
    norm_user = username.lower()

    conn = get_db()
    try:
        usage = _get_frontend_usage(conn, norm_user, period)
        if usage["bonus_unlocked"]:
            return False

        # Count unique solved challenges this calendar month.
        # frontend_submissions.created_at is ISO-8601, so prefix-matching the
        # YYYY-MM is sufficient and avoids loading rows.
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT challenge_id) AS solved_count
              FROM frontend_submissions
             WHERE username = ?
               AND solved = 1
               AND substr(created_at, 1, 7) = ?
            """,
            [norm_user, period],
        ).fetchone()
        solved_count = (row["solved_count"] if row else 0) or 0
        if solved_count < FRONTEND_FREE_BASE:
            return False

        conn.execute(
            """
            INSERT INTO frontend_usage (username, period_month, accessed_ids, bonus_unlocked)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(username, period_month) DO UPDATE SET bonus_unlocked = 1
            """,
            [norm_user, period, json.dumps(usage["accessed_ids"])],
        )
        conn.commit()
        return True
    finally:
        conn.close()


# ─── Streak freezes — monthly allowance ───────────────────────────────────────

FREEZE_ALLOWANCE = {"free": 2, "plus": 5}


def _ensure_freeze_period(conn, username: str, tier: str) -> Dict:
    """If the stored period key != current month, reset balance to tier allowance."""
    row = conn.execute(
        "SELECT streak_freezes_remaining, streak_freezes_period_key FROM users WHERE username = ?",
        [username],
    ).fetchone()
    if not row:
        return {"remaining": 0, "period_key": None}

    period = current_month()
    stored_key = row["streak_freezes_period_key"]
    if stored_key != period:
        new_balance = FREEZE_ALLOWANCE.get(tier, 1)
        conn.execute(
            """
            UPDATE users
               SET streak_freezes_remaining = ?,
                   streak_freezes_period_key = ?
             WHERE username = ?
            """,
            [new_balance, period, username],
        )
        conn.commit()
        return {"remaining": new_balance, "period_key": period}

    return {
        "remaining": (row["streak_freezes_remaining"] or 0),
        "period_key": stored_key,
    }


def freeze_status(username: str) -> Dict:
    """Return current freeze balance + monthly allowance for the user's tier."""
    tier = get_tier(username)
    norm_user = username.lower()
    conn = get_db()
    try:
        info = _ensure_freeze_period(conn, norm_user, tier)
        return {
            "tier": tier,
            "remaining": info["remaining"],
            "monthly_allowance": FREEZE_ALLOWANCE.get(tier, 1),
            "period_key": info["period_key"] or current_month(),
        }
    finally:
        conn.close()


def is_day_freeze_protected(username: str, date_str: str) -> bool:
    """Has the user used a streak freeze on this date?"""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT 1 FROM streak_freeze_log WHERE username = ? AND used_date = ?",
            [username.lower(), date_str],
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def consume_streak_freeze(username: str, date_str: str) -> Dict:
    """Use one freeze for `date_str`. Returns {success, remaining, error?}."""
    tier = get_tier(username)
    norm_user = username.lower()
    today = today_str()

    if date_str >= today:
        return {"success": False, "error": "Freezes can only be applied to past missed days"}

    conn = get_db()
    try:
        info = _ensure_freeze_period(conn, norm_user, tier)
        if info["remaining"] <= 0:
            return {"success": False, "error": "No streak freezes remaining this month"}

        # Already protected (either by completion or earlier freeze use).
        completed = conn.execute(
            "SELECT 1 FROM daily_completions WHERE username = ? AND date = ?",
            [norm_user, date_str],
        ).fetchone()
        if completed:
            return {"success": False, "error": "Already completed that day"}

        already_frozen = conn.execute(
            "SELECT 1 FROM streak_freeze_log WHERE username = ? AND used_date = ?",
            [norm_user, date_str],
        ).fetchone()
        if already_frozen:
            return {"success": False, "error": "Day already protected by a freeze"}

        conn.execute(
            """
            INSERT INTO streak_freeze_log (username, period_month, used_date, created_at)
            VALUES (?, ?, ?, ?)
            """,
            [norm_user, current_month(), date_str, datetime.now(timezone.utc).isoformat()],
        )
        new_balance = info["remaining"] - 1
        conn.execute(
            "UPDATE users SET streak_freezes_remaining = ? WHERE username = ?",
            [new_balance, norm_user],
        )
        conn.commit()
        return {"success": True, "remaining": new_balance}
    finally:
        conn.close()
