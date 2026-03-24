"""
YeetCode database operations — SQLite backend

Replaces DynamoDB + cache + WAL architecture.
All reads/writes go directly to SQLite (WAL mode, immediately durable).

S3 is kept only for daily backups (see backup.py).
"""

import os
import json
import time
import uuid
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List

from db import get_db
from logger import debug, info, warning, error, duel_action, duel_check, submission_check
from dotenv import load_dotenv

load_dotenv()

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_int(val, default: int = 0) -> int:
    """Coerce a SQLite value to int. Handles bytes (BLOB-stored ints from migration)."""
    if val is None:
        return default
    if isinstance(val, (bytes, bytearray)):
        # SQLite migration stored integers as little-endian BLOB
        return int.from_bytes(val, "little")
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


_INT_FIELDS = {
    "easy", "medium", "hard", "xp", "streak", "today", "leetcode_invalid",
    "wager_amount", "challenger_wager", "challengee_wager",
    "challenger_time", "challengee_time", "expires_at",
    "count", "expiry_date", "start_date", "xp_reward",
}

def _row_to_dict(row) -> Optional[Dict]:
    """Convert sqlite3.Row to plain dict, coercing BLOB ints, adding total_xp."""
    if row is None:
        return None
    d = dict(row)
    # Coerce any integer fields stored as BLOB bytes from the DynamoDB migration
    for field in _INT_FIELDS:
        if field in d and isinstance(d[field], (bytes, bytearray)):
            d[field] = _safe_int(d[field])
    easy   = _safe_int(d.get("easy"))
    medium = _safe_int(d.get("medium"))
    hard   = _safe_int(d.get("hard"))
    bonus  = _safe_int(d.get("xp"))
    d["total_xp"] = easy * 100 + medium * 300 + hard * 500 + bonus
    return d


def _calc_total_xp(user: Dict) -> int:
    """Compute total XP = difficulty XP + bonus XP."""
    easy   = _safe_int(user.get("easy"))
    medium = _safe_int(user.get("medium"))
    hard   = _safe_int(user.get("hard"))
    bonus  = _safe_int(user.get("xp"))
    return easy * 100 + medium * 300 + hard * 500 + bonus


def _user_row_to_leaderboard(user: Dict) -> Dict:
    """Project a user row into the shape expected by leaderboard endpoints."""
    display_name = user.get("display_name") or user.get("username", "")
    if not display_name or display_name == "undefined":
        display_name = user.get("username", "")
    return {
        "username": user.get("username", ""),
        "name":     display_name,
        "easy":     _safe_int(user.get("easy")),
        "medium":   _safe_int(user.get("medium")),
        "hard":     _safe_int(user.get("hard")),
        "today":    _safe_int(user.get("today")),
        "xp":       _calc_total_xp(user),
        "group_id": user.get("group_id"),
    }


# Backward-compat shim — items from SQLite are already plain dicts
def normalize_dynamodb_item(item: Dict) -> Dict:
    return item


# ---------------------------------------------------------------------------
# UserOperations
# ---------------------------------------------------------------------------

class UserOperations:

    @staticmethod
    def get_user_data(username: str) -> Optional[Dict]:
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", [username.lower()]
            ).fetchone()
            return _row_to_dict(row)
        except Exception as e:
            error(f"get_user_data failed for {username}: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def get_user_by_email(email: str) -> Optional[Dict]:
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?", [email.lower()]
            ).fetchone()
            return _row_to_dict(row)
        except Exception as e:
            error(f"get_user_by_email failed for {email}: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def create_user_with_username(
        username: str, email: str, display_name: str = None, university: str = None
    ) -> Dict:
        norm_user  = username.lower()
        norm_email = email.lower()
        now        = datetime.now(timezone.utc).isoformat()

        conn = get_db()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO users
                    (username, email, display_name, university, created_at, updated_at)
                VALUES (?,?,?,?,?,?)
                """,
                (norm_user, norm_email, display_name or username, university, now, now),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", [norm_user]
            ).fetchone()
            return _row_to_dict(row)
        except Exception as e:
            error(f"create_user_with_username failed for {username}: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def update_user_data(username: str, updates: Dict) -> bool:
        """
        updates: plain dict of field → value (no DynamoDB type wrappers).
        """
        if not updates:
            return True
        norm_user = username.lower()
        now = datetime.now(timezone.utc).isoformat()
        updates["updated_at"] = now

        fields = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [norm_user]

        conn = get_db()
        try:
            conn.execute(
                f"UPDATE users SET {fields} WHERE username = ?", values
            )
            conn.commit()
            return True
        except Exception as e:
            error(f"update_user_data failed for {username}: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def award_xp(username: str, xp_amount: int) -> bool:
        """Atomically increment bonus XP (negative for wager losses)."""
        conn = get_db()
        try:
            conn.execute(
                "UPDATE users SET xp = xp + ? WHERE username = ?",
                [xp_amount, username.lower()],
            )
            conn.commit()
            return True
        except Exception as e:
            error(f"award_xp failed for {username}: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def get_leaderboard() -> Dict:
        conn = get_db()
        try:
            rows = conn.execute(
                """
                SELECT * FROM users
                WHERE username NOT LIKE 'verification_%'
                  AND leetcode_invalid = 0
                """
            ).fetchall()
            users = [_user_row_to_leaderboard(_row_to_dict(r)) for r in rows]
            return {"success": True, "data": users}
        except Exception as e:
            error(f"get_leaderboard failed: {e}")
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    @staticmethod
    def get_all_users_for_university_leaderboard() -> Dict:
        conn = get_db()
        try:
            rows = conn.execute(
                """
                SELECT username, display_name, university, easy, medium, hard, xp
                FROM users
                WHERE university IS NOT NULL
                  AND university != ''
                  AND university != 'undefined'
                  AND university != 'Other'
                  AND username NOT LIKE 'verification_%'
                """
            ).fetchall()
            users = [_row_to_dict(r) for r in rows]
            return {"success": True, "data": users}
        except Exception as e:
            error(f"get_all_users_for_university_leaderboard failed: {e}")
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    @staticmethod
    def get_all_users() -> Dict:
        """Return all non-verification users as plain dicts."""
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM users WHERE username NOT LIKE 'verification_%'"
            ).fetchall()
            users = [_row_to_dict(r) for r in rows]
            return {"success": True, "data": users}
        except Exception as e:
            error(f"get_all_users failed: {e}")
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    @staticmethod
    def get_group_users(group_id: str) -> Dict:
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM users WHERE group_id = ?", [group_id]
            ).fetchall()
            users = [_user_row_to_leaderboard(_row_to_dict(r)) for r in rows]
            return {"success": True, "data": users}
        except Exception as e:
            error(f"get_group_users failed for {group_id}: {e}")
            return {"success": False, "error": str(e)}
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# VerificationOperations
# ---------------------------------------------------------------------------

class VerificationOperations:

    @staticmethod
    def store_verification_code(email: str, code: str) -> bool:
        norm_email = email.lower()
        expires_at = int(time.time()) + 10 * 60  # 10 minutes

        conn = get_db()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO verification_codes (email, code, expires_at) VALUES (?,?,?)",
                [norm_email, code, expires_at],
            )
            conn.commit()
            return True
        except Exception as e:
            error(f"store_verification_code failed for {email}: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def verify_code_and_get_user(email: str, code: str) -> Dict:
        norm_email = email.lower()
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM verification_codes WHERE email = ?", [norm_email]
            ).fetchone()

            if not row:
                return {"success": False, "error": "Verification code not found"}
            if time.time() > row["expires_at"]:
                return {"success": False, "error": "Verification code expired"}
            if row["code"] != code:
                return {"success": False, "error": "Invalid verification code"}

            conn.execute(
                "DELETE FROM verification_codes WHERE email = ?", [norm_email]
            )
            conn.commit()

            user = UserOperations.get_user_by_email(norm_email)
            return {"success": True, "data": user}
        except Exception as e:
            error(f"verify_code_and_get_user failed for {email}: {e}")
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    @staticmethod
    def cleanup_expired_codes() -> Dict:
        now = int(time.time())
        conn = get_db()
        try:
            cur = conn.execute(
                "DELETE FROM verification_codes WHERE expires_at < ?", [now]
            )
            conn.commit()
            return {"success": True, "count": cur.rowcount}
        except Exception as e:
            error(f"cleanup_expired_codes failed: {e}")
            return {"success": False, "count": 0}
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# GroupOperations
# ---------------------------------------------------------------------------

class GroupOperations:

    @staticmethod
    def create_group(username: str, display_name: Optional[str] = None) -> Dict:
        norm_user = username.lower()
        group_id  = str(random.randint(10000, 99999))
        now       = datetime.now(timezone.utc).isoformat()

        conn = get_db()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO groups (group_id, leader, created_at) VALUES (?,?,?)",
                [group_id, norm_user, now],
            )
            conn.execute(
                "UPDATE users SET group_id = ?, display_name = COALESCE(?, display_name), updated_at = ? WHERE username = ?",
                [group_id, display_name or username, now, norm_user],
            )
            conn.commit()
            return {"success": True, "group_id": group_id}
        except Exception as e:
            error(f"create_group failed for {username}: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def join_group(username: str, invite_code: str, display_name: Optional[str] = None) -> Dict:
        norm_user = username.lower()
        now       = datetime.now(timezone.utc).isoformat()

        conn = get_db()
        try:
            conn.execute(
                "UPDATE users SET group_id = ?, display_name = COALESCE(?, display_name), updated_at = ? WHERE username = ?",
                [invite_code, display_name or username, now, norm_user],
            )
            conn.commit()
            return {"success": True, "group_id": invite_code}
        except Exception as e:
            error(f"join_group failed for {username}: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def leave_group(username: str) -> Dict:
        norm_user = username.lower()
        now       = datetime.now(timezone.utc).isoformat()

        conn = get_db()
        try:
            conn.execute(
                "UPDATE users SET group_id = NULL, updated_at = ? WHERE username = ?",
                [now, norm_user],
            )
            conn.commit()
            return {"success": True}
        except Exception as e:
            error(f"leave_group failed for {username}: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def get_group_stats(group_id: str) -> Dict:
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM users WHERE group_id = ?", [group_id]
            ).fetchall()
            leaderboard = []
            for row in rows:
                u = _row_to_dict(row)
                display_name = u.get("display_name") or u.get("username", "")
                if not display_name or display_name == "undefined":
                    display_name = u.get("username", "")
                leaderboard.append({
                    "username": u.get("username", ""),
                    "name":     display_name,
                    "easy":     _safe_int(u.get("easy")),
                    "medium":   _safe_int(u.get("medium")),
                    "hard":     _safe_int(u.get("hard")),
                    "today":    _safe_int(u.get("today")),
                    "xp":       _calc_total_xp(u),
                })
            return {"success": True, "data": leaderboard}
        except Exception as e:
            error(f"get_group_stats failed for {group_id}: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def get_all_groups() -> Dict:
        conn = get_db()
        try:
            rows = conn.execute("SELECT * FROM groups").fetchall()
            groups = [_row_to_dict(r) for r in rows]
            return {"success": True, "data": groups}
        except Exception as e:
            error(f"get_all_groups failed: {e}")
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    @staticmethod
    def get_group_by_id(group_id: str) -> Dict:
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM groups WHERE group_id = ?", [group_id]
            ).fetchone()
            if row:
                return {"success": True, "data": _row_to_dict(row)}
            return {"success": False, "error": "Group not found"}
        except Exception as e:
            error(f"get_group_by_id failed for {group_id}: {e}")
            return {"success": False, "error": str(e)}
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# DailyProblemOperations
# ---------------------------------------------------------------------------

class DailyProblemOperations:

    @staticmethod
    def get_daily_problem_data(username: str) -> Dict:
        """Get today's daily problem + user completion status + streak."""
        today     = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        norm_user = username.lower()

        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM daily_problems WHERE date = ?", [today]
            ).fetchone()

            if not row:
                row = conn.execute(
                    "SELECT * FROM daily_problems ORDER BY date DESC LIMIT 1"
                ).fetchone()

            latest_problem = None
            if row:
                p = _row_to_dict(row)
                tags = []
                try:
                    tags = json.loads(p.get("tags") or "[]")
                except Exception:
                    pass
                latest_problem = {
                    "date":       p["date"],
                    "titleSlug":  p["slug"],
                    "title":      p.get("title"),
                    "frontendId": p.get("frontend_id"),
                    "topicTags":  tags,
                    "difficulty": p.get("difficulty"),  # None if not stored — no fake default
                    "content":    p.get("content", ""),
                }

            daily_complete = False
            if latest_problem:
                done = conn.execute(
                    "SELECT 1 FROM daily_completions WHERE username = ? AND date = ?",
                    [norm_user, latest_problem["date"]],
                ).fetchone()
                daily_complete = done is not None

            streak = DailyProblemOperations._calc_streak(conn, norm_user)

            return {
                "success": True,
                "data": {
                    "dailyComplete": daily_complete,
                    "streak":        streak,
                    "todaysProblem": latest_problem,
                    "error":         None,
                },
            }
        except Exception as e:
            error(f"get_daily_problem_data failed for {username}: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def _calc_streak(conn, username: str) -> int:
        """Count consecutive completed days ending at today (or yesterday)."""
        today = datetime.now(timezone.utc).date()
        rows  = conn.execute(
            "SELECT date FROM daily_completions WHERE username = ? ORDER BY date DESC",
            [username],
        ).fetchall()
        dates = {row["date"] for row in rows}

        streak = 0
        check  = today
        if today.strftime("%Y-%m-%d") not in dates:
            check = today - timedelta(days=1)

        while check.strftime("%Y-%m-%d") in dates:
            streak += 1
            check  -= timedelta(days=1)

        return streak

    @staticmethod
    def get_user_daily_data(username: str) -> Dict:
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT streak, last_completed_date FROM users WHERE username = ?",
                [username.lower()],
            ).fetchone()
            if row:
                return {
                    "streak":              row["streak"] or 0,
                    "last_completed_date": row["last_completed_date"],
                }
            return {"streak": 0, "last_completed_date": None}
        except Exception as e:
            error(f"get_user_daily_data failed for {username}: {e}")
            return {"streak": 0, "last_completed_date": None}
        finally:
            conn.close()

    @staticmethod
    def complete_daily_problem(username: str) -> Dict:
        """Mark today's daily as completed, update streak, award 200 XP."""
        today     = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        norm_user = username.lower()
        now_iso   = datetime.now(timezone.utc).isoformat()

        conn = get_db()
        try:
            already = conn.execute(
                "SELECT 1 FROM daily_completions WHERE username = ? AND date = ?",
                [norm_user, today],
            ).fetchone()

            if already:
                return {"success": True, "message": "Already completed today"}

            conn.execute(
                "INSERT OR IGNORE INTO daily_completions (username, date) VALUES (?,?)",
                [norm_user, today],
            )

            user_row = conn.execute(
                "SELECT streak, last_completed_date FROM users WHERE username = ?",
                [norm_user],
            ).fetchone()

            current_streak = user_row["streak"] if user_row else 0
            last_date      = user_row["last_completed_date"] if user_row else None

            new_streak = current_streak + 1 if last_date == yesterday else 1

            conn.execute(
                """
                UPDATE users
                SET streak = ?, last_completed_date = ?, today = 1,
                    xp = xp + 200, updated_at = ?
                WHERE username = ?
                """,
                [new_streak, today, now_iso, norm_user],
            )
            conn.commit()

            info(f"✅ {norm_user} completed daily — streak={new_streak}, +200 XP")
            return {"success": True, "streak": new_streak}
        except Exception as e:
            error(f"complete_daily_problem failed for {username}: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def get_top_daily_problems() -> Dict:
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM daily_problems ORDER BY date DESC LIMIT 2"
            ).fetchall()
            problems = []
            for row in rows:
                p = _row_to_dict(row)
                tags = []
                try:
                    tags = json.loads(p.get("tags") or "[]")
                except Exception:
                    pass
                problems.append({
                    "date":       p["date"],
                    "titleSlug":  p["slug"],
                    "title":      p.get("title"),
                    "frontendId": p.get("frontend_id"),
                    "topicTags":  tags,
                    "difficulty": p.get("difficulty"),
                    "content":    p.get("content", ""),
                })
            return {"success": True, "data": problems}
        except Exception as e:
            error(f"get_top_daily_problems failed: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def get_todays_completions() -> Dict:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        conn  = get_db()
        try:
            rows = conn.execute(
                "SELECT username FROM daily_completions WHERE date = ?", [today]
            ).fetchall()
            users = {row["username"]: True for row in rows}
            return {
                "success": True,
                "data": {"users": users, "problem_date": today},
            }
        except Exception as e:
            error(f"get_todays_completions failed: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def save_daily_problem(date: str, slug: str, title: str,
                           frontend_id: str, difficulty: str, tags: List[str]) -> bool:
        """Upsert daily problem row (called by generate_daily_problem in background_tasks)."""
        conn = get_db()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO daily_problems
                    (date, slug, title, frontend_id, difficulty, tags)
                VALUES (?,?,?,?,?,?)
                """,
                [date, slug, title, frontend_id, difficulty, json.dumps(tags)],
            )
            conn.commit()
            return True
        except Exception as e:
            error(f"save_daily_problem failed: {e}")
            return False
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# BountyOperations
# ---------------------------------------------------------------------------

class BountyOperations:

    @staticmethod
    def _enrich_bounty(row: Dict, user_progress: int = 0, current_time: int = None) -> Dict:
        if current_time is None:
            current_time = int(time.time())

        b           = dict(row)
        count       = _safe_int(b.get("count"))
        expiry_date = _safe_int(b.get("expiry_date"))
        start_date  = _safe_int(b.get("start_date"))

        b["bountyId"] = b.get("bounty_id")
        b["id"]       = b.get("bounty_id")
        b["isActive"]  = start_date <= current_time <= expiry_date
        b["isExpired"] = current_time > expiry_date

        time_remaining      = max(0, expiry_date - current_time)
        b["timeRemaining"]  = time_remaining
        b["daysRemaining"]  = time_remaining // (24 * 3600)
        b["hoursRemaining"] = (time_remaining % (24 * 3600)) // 3600
        b["userProgress"]   = user_progress
        b["progressPercent"] = min(
            (user_progress / count) * 100 if count > 0 else 0, 100
        )
        return b

    @staticmethod
    def get_user_bounties(username: str) -> Dict:
        norm_user    = username.lower()
        current_time = int(time.time())

        conn = get_db()
        try:
            rows = conn.execute(
                """
                SELECT b.*, COALESCE(bp.progress, 0) AS user_progress
                FROM bounties b
                LEFT JOIN bounty_progress bp
                    ON bp.bounty_id = b.bounty_id AND bp.username = ?
                WHERE b.start_date <= ? AND b.expiry_date >= ?
                """,
                [norm_user, current_time, current_time],
            ).fetchall()

            bounties = [
                BountyOperations._enrich_bounty(
                    _row_to_dict(r),
                    user_progress=r["user_progress"],
                    current_time=current_time,
                )
                for r in rows
            ]
            return {"success": True, "data": bounties}
        except Exception as e:
            error(f"get_user_bounties failed for {username}: {e}")
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    @staticmethod
    def get_all_bounties() -> Dict:
        conn = get_db()
        try:
            rows = conn.execute("SELECT * FROM bounties").fetchall()
            bounties = []
            for r in rows:
                d = _row_to_dict(r)
                d["bountyId"] = d.get("bounty_id")
                d["id"]       = d.get("bounty_id")
                bounties.append(d)
            return {"success": True, "data": bounties}
        except Exception as e:
            error(f"get_all_bounties failed: {e}")
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    @staticmethod
    def get_bounty_by_id(bounty_id: str) -> Dict:
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM bounties WHERE bounty_id = ?", [bounty_id]
            ).fetchone()
            if row:
                d = _row_to_dict(row)
                d["bountyId"] = d["bounty_id"]
                d["id"]       = d["bounty_id"]
                return {"success": True, "data": d}
            return {"success": False, "error": "Bounty not found"}
        except Exception as e:
            error(f"get_bounty_by_id failed for {bounty_id}: {e}")
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    @staticmethod
    def get_bounty_progress(bounty_id: str) -> Dict:
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT username, progress FROM bounty_progress WHERE bounty_id = ?",
                [bounty_id],
            ).fetchall()
            progress = {row["username"]: row["progress"] for row in rows}
            return {"success": True, "data": progress}
        except Exception as e:
            error(f"get_bounty_progress failed for {bounty_id}: {e}")
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    @staticmethod
    def update_bounty_progress(username: str, bounty_id: str, new_progress: int,
                               xp_reward: int = 0) -> Dict:
        """Upsert bounty progress. Awards XP if newly completed."""
        norm_user = username.lower()
        conn = get_db()
        try:
            # Check previous progress
            prev = conn.execute(
                "SELECT progress FROM bounty_progress WHERE bounty_id = ? AND username = ?",
                [bounty_id, norm_user],
            ).fetchone()
            prev_progress = prev["progress"] if prev else 0

            # Get bounty count requirement
            bounty_row = conn.execute(
                "SELECT count FROM bounties WHERE bounty_id = ?", [bounty_id]
            ).fetchone()
            if not bounty_row:
                return {"success": False, "error": "Bounty not found"}
            required_count = bounty_row["count"]

            conn.execute(
                """
                INSERT INTO bounty_progress (bounty_id, username, progress)
                VALUES (?,?,?)
                ON CONFLICT(bounty_id, username) DO UPDATE SET progress = excluded.progress
                """,
                [bounty_id, norm_user, new_progress],
            )
            conn.commit()

            just_completed = prev_progress < required_count and new_progress >= required_count
            if just_completed and xp_reward > 0:
                UserOperations.award_xp(norm_user, xp_reward)
                info(f"✅ {norm_user} completed bounty {bounty_id}, awarded {xp_reward} XP")
                return {
                    "success": True, "progress": new_progress,
                    "completed": True, "xp_awarded": xp_reward,
                }

            return {
                "success": True, "progress": new_progress,
                "completed": just_completed,
                "progress_percent": (new_progress / required_count * 100) if required_count > 0 else 0,
            }
        except Exception as e:
            error(f"update_bounty_progress failed for {username}/{bounty_id}: {e}")
            return {"success": False, "error": str(e)}
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# DuelOperations
# ---------------------------------------------------------------------------

class DuelOperations:

    @staticmethod
    def _row_to_duel(row) -> Dict:
        if row is None:
            return None
        d = _row_to_dict(row)
        d["is_wager"] = bool(d.get("is_wager"))
        # camelCase aliases for frontend compatibility
        d["duelId"]               = d.get("duel_id")
        d["problemSlug"]          = d.get("problem_slug")
        d["problemTitle"]         = d.get("problem_title")
        d["problemNumber"]        = d.get("problem_number")
        d["isWager"]              = d.get("is_wager")
        d["challengerWager"]      = d.get("challenger_wager")
        d["challengeeWager"]      = d.get("challengee_wager")
        d["challengerTime"]       = d.get("challenger_time")
        d["challengeeTime"]       = d.get("challengee_time")
        d["challengerStartTime"]  = d.get("challenger_start_time")
        d["challengeeStartTime"]  = d.get("challengee_start_time")
        d["startTime"]            = d.get("start_time")
        d["xpAwarded"]            = d.get("xp_awarded")
        d["createdAt"]            = d.get("created_at")
        d["acceptedAt"]           = d.get("accepted_at")
        d["completedAt"]          = d.get("completed_at")
        d["expiresAt"]            = d.get("expires_at")
        return d

    @staticmethod
    def get_user_duels(username: str) -> Dict:
        norm_user = username.lower()
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM duels WHERE challenger = ? OR challengee = ?",
                [norm_user, norm_user],
            ).fetchall()
            duels = [DuelOperations._row_to_duel(r) for r in rows]
            return {"success": True, "data": duels}
        except Exception as e:
            error(f"get_user_duels failed for {username}: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def get_all_duels() -> Dict:
        conn = get_db()
        try:
            rows = conn.execute("SELECT * FROM duels").fetchall()
            duels = [DuelOperations._row_to_duel(r) for r in rows]
            return {"success": True, "data": duels}
        except Exception as e:
            error(f"get_all_duels failed: {e}")
            return {"success": False, "data": [], "error": str(e)}
        finally:
            conn.close()

    @staticmethod
    def get_duel_by_id(duel_id: str) -> Dict:
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM duels WHERE duel_id = ?", [duel_id]
            ).fetchone()
            if row:
                return {"success": True, "data": DuelOperations._row_to_duel(row)}
            return {"success": False, "error": "Duel not found"}
        except Exception as e:
            error(f"get_duel_by_id failed for {duel_id}: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def create_duel(
        username: str, opponent: str, problem_slug: str,
        problem_title: str = None, problem_number: str = None,
        difficulty: str = None, is_wager: bool = False,
        wager_amount: int = None,
    ) -> Dict:
        norm_user     = username.lower()
        norm_opponent = opponent.lower()
        duel_id       = str(uuid.uuid4())
        now_iso       = datetime.now(timezone.utc).isoformat()
        expires_at    = int(time.time()) + 3600  # 1 hour

        if is_wager:
            if not wager_amount or wager_amount < 25:
                raise Exception("Wager amount must be at least 25 XP")
            challenger_data = UserOperations.get_user_data(norm_user)
            if not challenger_data:
                raise Exception(f"Challenger not found: {norm_user}")
            if _calc_total_xp(challenger_data) < wager_amount:
                raise Exception(f"Challenger has insufficient XP (needs {wager_amount})")

        conn = get_db()
        try:
            conn.execute(
                """
                INSERT INTO duels
                    (duel_id, challenger, challengee, problem_slug, problem_title,
                     problem_number, difficulty, status, is_wager, challenger_wager,
                     created_at, expires_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                [
                    duel_id, norm_user, norm_opponent,
                    problem_slug, problem_title, problem_number,
                    difficulty, "PENDING",
                    1 if is_wager else 0,
                    wager_amount or 0,
                    now_iso, expires_at,
                ],
            )
            conn.commit()
            duel_action(
                f"Created duel {duel_id}",
                challenger=norm_user, challengee=norm_opponent, problem=problem_slug
            )
            try:
                from push_service import send_push
                challenger_data = UserOperations.get_user_data(norm_user)
                display = (challenger_data or {}).get("display_name") or norm_user
                send_push(norm_opponent, "⚔️ Duel Challenge!", f"{display} challenged you to a duel!")
            except Exception:
                pass
            return {"success": True, "data": {"duel_id": duel_id}}
        except Exception as e:
            error(f"create_duel failed: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def accept_duel(username: str, duel_id: str, opponent_wager: int = None) -> Dict:
        norm_user = username.lower()
        now_iso   = datetime.now(timezone.utc).isoformat()

        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM duels WHERE duel_id = ?", [duel_id]
            ).fetchone()
            if not row:
                raise Exception("Duel not found")

            duel = _row_to_dict(row)
            is_wager         = bool(duel.get("is_wager"))
            challenger_wager = _safe_int(duel.get("challenger_wager"))

            # Symmetric wager model: challengee always stakes the same amount as challenger
            challengee_wager = 0
            if is_wager and challenger_wager > 0:
                challengee_wager = challenger_wager
                opp_data = UserOperations.get_user_data(norm_user)
                if not opp_data or _calc_total_xp(opp_data) < challengee_wager:
                    raise Exception(f"You need at least {challengee_wager} XP to accept this wager duel")

            conn.execute(
                """
                UPDATE duels
                SET status = 'ACCEPTED', accepted_at = ?, challengee_wager = ?
                WHERE duel_id = ?
                """,
                [now_iso, challengee_wager, duel_id],
            )
            conn.commit()
            duel_action(f"User {username} accepted duel {duel_id}")
            try:
                from push_service import send_push
                acceptee_data = UserOperations.get_user_data(norm_user)
                display = (acceptee_data or {}).get("display_name") or norm_user
                challenger = duel.get("challenger", "")
                send_push(challenger, "✅ Duel Accepted!", f"{display} accepted your duel challenge!")
            except Exception:
                pass
            return {"success": True}
        except Exception as e:
            error(f"accept_duel failed for {duel_id}: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def start_duel(username: str, duel_id: str) -> Dict:
        norm_user = username.lower()
        now_iso   = datetime.now(timezone.utc).isoformat()

        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM duels WHERE duel_id = ?", [duel_id]
            ).fetchone()
            if not row:
                raise Exception("Duel not found")

            duel = _row_to_dict(row)
            if norm_user == duel["challenger"]:
                conn.execute(
                    """
                    UPDATE duels
                    SET challenger_time = 0, challenger_start_time = ?,
                        status = 'ACTIVE', start_time = COALESCE(start_time, ?)
                    WHERE duel_id = ?
                    """,
                    [now_iso, now_iso, duel_id],
                )
            elif norm_user == duel["challengee"]:
                conn.execute(
                    """
                    UPDATE duels
                    SET challengee_time = 0, challengee_start_time = ?,
                        status = 'ACTIVE', start_time = COALESCE(start_time, ?)
                    WHERE duel_id = ?
                    """,
                    [now_iso, now_iso, duel_id],
                )
            else:
                raise Exception("User is not part of this duel")

            conn.commit()
            duel_action(f"User {username} started duel {duel_id}")
            return {"success": True, "message": f"Duel started for {username}"}
        except Exception as e:
            error(f"start_duel failed for {duel_id}: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def reject_duel(duel_id: str) -> Dict:
        conn = get_db()
        try:
            conn.execute("DELETE FROM duels WHERE duel_id = ?", [duel_id])
            conn.commit()
            return {"success": True, "duel_id": duel_id}
        except Exception as e:
            error(f"reject_duel failed for {duel_id}: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def calculate_duel_xp(difficulty: str, is_winner: bool) -> int:
        return 200 if is_winner else 0

    @staticmethod
    def record_duel_submission(username: str, duel_id: str, elapsed_ms: int) -> Dict:
        norm_user = username.lower()
        now_ts    = datetime.now(timezone.utc)
        now_iso   = now_ts.isoformat()

        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM duels WHERE duel_id = ?", [duel_id]
            ).fetchone()
            if not row:
                return {"success": False, "error": "Duel not found"}

            duel       = _row_to_dict(row)
            challenger = duel["challenger"]
            challengee = duel["challengee"]

            if duel["status"] == "COMPLETED":
                return {"success": False, "error": "Duel already completed"}

            is_challenger = norm_user == challenger
            if not is_challenger and norm_user != challengee:
                return {"success": False, "error": "User not part of this duel"}

            if is_challenger and duel["challenger_time"] not in (-1, 0):
                return {"success": False, "error": "Challenger time already recorded"}
            if not is_challenger and duel["challengee_time"] not in (-1, 0):
                return {"success": False, "error": "Challengee time already recorded"}

            start_field = "challenger_start_time" if is_challenger else "challengee_start_time"
            start_str   = duel.get(start_field)
            if start_str:
                try:
                    user_start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    actual_ms  = int((now_ts - user_start).total_seconds() * 1000)
                except Exception:
                    actual_ms = elapsed_ms
            else:
                actual_ms = elapsed_ms

            time_field = "challenger_time" if is_challenger else "challengee_time"
            conn.execute(
                f"UPDATE duels SET {time_field} = ? WHERE duel_id = ?",
                [actual_ms, duel_id],
            )
            conn.commit()

            # Re-read to check completion
            duel = _row_to_dict(conn.execute(
                "SELECT * FROM duels WHERE duel_id = ?", [duel_id]
            ).fetchone())

            new_challenger_time = duel["challenger_time"] if duel["challenger_time"] > 0 else None
            new_challengee_time = duel["challengee_time"] if duel["challengee_time"] > 0 else None
            should_complete     = new_challenger_time is not None and new_challengee_time is not None

            winner   = None
            total_xp = 0

            if should_complete:
                difficulty   = duel.get("difficulty", "Medium")
                is_wager     = bool(duel.get("is_wager"))
                chall_wager  = int(duel.get("challenger_wager")  or 0)
                chalee_wager = _safe_int(duel.get("challengee_wager"))

                if new_challenger_time < new_challengee_time:
                    winner = challenger
                elif new_challengee_time < new_challenger_time:
                    winner = challengee

                if is_wager and (chall_wager > 0 or chalee_wager > 0):
                    if winner:
                        w_wager  = chall_wager  if winner == challenger else chalee_wager
                        loser    = challengee   if winner == challenger else challenger
                        l_wager  = chalee_wager if winner == challenger else chall_wager
                        bonus    = DuelOperations.calculate_duel_xp(difficulty, True)
                        total_xp = w_wager + l_wager + bonus
                        UserOperations.award_xp(winner, w_wager + l_wager)
                        UserOperations.award_xp(winner, bonus)
                        UserOperations.award_xp(loser,  -l_wager)
                        duel_action(f"Wager duel {duel_id}: {winner} won {total_xp} XP", winner=winner)
                else:
                    bonus    = DuelOperations.calculate_duel_xp(difficulty, True)
                    total_xp = bonus
                    if winner:
                        loser = challengee if winner == challenger else challenger
                        UserOperations.award_xp(winner, bonus)
                        UserOperations.award_xp(loser, 25)
                    else:
                        UserOperations.award_xp(challenger, bonus)
                        UserOperations.award_xp(challengee, bonus)
                    duel_action(f"Duel {duel_id} completed", winner=winner or "TIE")

                conn.execute(
                    """
                    UPDATE duels
                    SET status = 'COMPLETED', winner = ?, xp_awarded = ?, completed_at = ?
                    WHERE duel_id = ?
                    """,
                    [winner, total_xp, now_iso, duel_id],
                )
                conn.commit()

                # Push result notifications
                try:
                    from push_service import send_push
                    loser = challengee if winner == challenger else challenger
                    if winner:
                        w_data = UserOperations.get_user_data(winner)
                        l_data = UserOperations.get_user_data(loser)
                        w_display = (w_data or {}).get("display_name") or winner
                        l_display = (l_data or {}).get("display_name") or loser
                        send_push(winner, "🏆 Duel Won!", f"You beat {l_display}! +{total_xp} XP")
                        send_push(loser,  "😤 Duel Lost", f"{w_display} beat you. Rematch?")
                    else:
                        send_push(challenger, "🤝 Duel Tied!", "It's a tie! Both players solved it.")
                        send_push(challengee, "🤝 Duel Tied!", "It's a tie! Both players solved it.")
                except Exception:
                    pass

            duel_action(f"User {norm_user} recorded time", duel_id=duel_id, time_ms=actual_ms)
            return {
                "success":   True,
                "completed": should_complete,
                "winner":    winner if should_complete else None,
                "xpAwarded": total_xp if should_complete else None,
            }
        except Exception as e:
            error(f"record_duel_submission failed for {duel_id}: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def handle_duel_timeouts() -> Dict:
        now     = int(time.time())
        now_iso = datetime.now(timezone.utc).isoformat()

        conn = get_db()
        try:
            expired = conn.execute(
                """
                SELECT * FROM duels
                WHERE status IN ('PENDING', 'ACTIVE')
                  AND expires_at < ?
                """,
                [now],
            ).fetchall()

            completed = 0
            for row in expired:
                duel = _row_to_dict(row)
                if duel["status"] == "PENDING":
                    conn.execute("DELETE FROM duels WHERE duel_id = ?", [duel["duel_id"]])
                else:
                    c_time = duel["challenger_time"]
                    e_time = duel["challengee_time"]
                    winner = None
                    if c_time > 0 and e_time <= 0:
                        winner = duel["challenger"]
                    elif e_time > 0 and c_time <= 0:
                        winner = duel["challengee"]
                    conn.execute(
                        """
                        UPDATE duels
                        SET status = 'COMPLETED', winner = ?, completed_at = ?
                        WHERE duel_id = ?
                        """,
                        [winner, now_iso, duel["duel_id"]],
                    )
                completed += 1

            conn.commit()
            return {"completed_duels": completed}
        except Exception as e:
            error(f"handle_duel_timeouts failed: {e}")
            return {"completed_duels": 0}
        finally:
            conn.close()

    @staticmethod
    def cleanup_expired_duels() -> Dict:
        now    = int(time.time())
        cutoff = now - 48 * 3600

        conn = get_db()
        try:
            cur = conn.execute(
                """
                DELETE FROM duels
                WHERE (status = 'COMPLETED' AND expires_at < ?)
                   OR (status = 'PENDING'   AND expires_at < ?)
                """,
                [cutoff, now],
            )
            # Also clean expired duel invites
            conn.execute("DELETE FROM duel_invites WHERE expires_at < ?", [now])
            conn.commit()
            return {"success": True, "count": cur.rowcount}
        except Exception as e:
            error(f"cleanup_expired_duels failed: {e}")
            return {"success": False, "count": 0}
        finally:
            conn.close()

    # ── Open challenges ──────────────────────────────────────────────────────

    @staticmethod
    def create_open_challenge(challenger: str, problem_slug: str, problem_title: str,
                               problem_number: str, difficulty: str,
                               is_wager: bool = False, wager_amount: int = None) -> Dict:
        """Create a duel open to any group member (challengee='OPEN')."""
        return DuelOperations.create_duel(
            challenger, "OPEN", problem_slug, problem_title,
            problem_number, difficulty, is_wager, wager_amount
        )

    @staticmethod
    def get_open_challenges(username: str, group_id: str) -> Dict:
        """Return PENDING open challenges from group members (excluding the requester)."""
        norm_user = username.lower()
        conn = get_db()
        try:
            rows = conn.execute(
                """
                SELECT d.* FROM duels d
                JOIN users u ON u.username = d.challenger
                WHERE d.challengee = 'open'
                  AND d.status = 'PENDING'
                  AND d.challenger != ?
                  AND u.group_id = ?
                  AND (d.problem_slug IS NOT NULL AND d.problem_slug != '')
                ORDER BY d.created_at DESC
                """,
                [norm_user, group_id],
            ).fetchall()
            return {"success": True, "data": [DuelOperations._row_to_duel(r) for r in rows]}
        except Exception as e:
            error(f"get_open_challenges failed: {e}")
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    @staticmethod
    def accept_open_challenge(username: str, duel_id: str) -> Dict:
        """Accept an open challenge — sets the challengee to the accepting user."""
        norm_user = username.lower()
        now_iso   = datetime.now(timezone.utc).isoformat()
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM duels WHERE duel_id = ? AND challengee = 'open' AND status = 'PENDING'",
                [duel_id]
            ).fetchone()
            if not row:
                raise Exception("Open challenge not found or already taken")

            duel = _row_to_dict(row)
            if duel["challenger"] == norm_user:
                raise Exception("You cannot accept your own open challenge")

            is_wager         = bool(duel.get("is_wager"))
            challenger_wager = _safe_int(duel.get("challenger_wager"))
            challengee_wager = 0

            if is_wager and challenger_wager > 0:
                challengee_wager = challenger_wager
                opp_data = UserOperations.get_user_data(norm_user)
                if not opp_data or _calc_total_xp(opp_data) < challengee_wager:
                    raise Exception(f"You need at least {challengee_wager} XP to accept this wager")

            conn.execute(
                """
                UPDATE duels
                SET challengee = ?, status = 'ACCEPTED', accepted_at = ?, challengee_wager = ?
                WHERE duel_id = ?
                """,
                [norm_user, now_iso, challengee_wager, duel_id],
            )
            conn.commit()
            duel_action(f"User {username} accepted open challenge {duel_id}")
            return {"success": True}
        except Exception as e:
            error(f"accept_open_challenge failed: {e}")
            raise
        finally:
            conn.close()

    # ── Duel invites (for non-users) ─────────────────────────────────────────

    @staticmethod
    def create_duel_invite(challenger: str, difficulty: str, email: str = None) -> Dict:
        """Create a shareable invite link. Optionally send to an email address."""
        import secrets
        token      = secrets.token_urlsafe(12)
        now_iso    = datetime.now(timezone.utc).isoformat()
        expires_at = int(time.time()) + 86400  # 24 hours

        conn = get_db()
        try:
            conn.execute(
                """
                INSERT INTO duel_invites (token, challenger, email, difficulty, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [token, challenger.lower(), email, difficulty or "EASY", now_iso, expires_at],
            )
            conn.commit()
            invite_url = f"https://yeetcode.xyz/duel-invite/{token}"

            if email:
                from email_service import send_duel_invite
                challenger_data = UserOperations.get_user_data(challenger)
                name = (challenger_data or {}).get("display_name") or challenger
                send_duel_invite(email, name, difficulty or "Easy", invite_url)

            return {"success": True, "token": token, "invite_url": invite_url}
        except Exception as e:
            error(f"create_duel_invite failed: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def get_duel_invite(token: str) -> Dict:
        """Return invite details for the landing page."""
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM duel_invites WHERE token = ?", [token]
            ).fetchone()
            if not row:
                return {"success": False, "error": "Invite not found or expired"}
            inv = dict(row)
            if int(time.time()) > inv["expires_at"]:
                return {"success": False, "error": "Invite has expired"}
            challenger_data = UserOperations.get_user_data(inv["challenger"])
            name = (challenger_data or {}).get("display_name") or inv["challenger"]
            return {
                "success":    True,
                "token":      token,
                "challenger": inv["challenger"],
                "challengerName": name,
                "difficulty": inv["difficulty"],
                "expiresAt":  inv["expires_at"],
            }
        except Exception as e:
            error(f"get_duel_invite failed: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def accept_duel_invite(token: str, username: str) -> Dict:
        """Convert an invite into a real duel. User must be authenticated."""
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM duel_invites WHERE token = ?", [token]
            ).fetchone()
            if not row:
                raise Exception("Invite not found or already used")
            inv = dict(row)
            if int(time.time()) > inv["expires_at"]:
                raise Exception("Invite has expired")

            from background_tasks import fetch_random_problem
            difficulty = inv.get("difficulty", "EASY").upper()
            problem = fetch_random_problem(difficulty)
            if not problem:
                raise Exception("Could not find a suitable problem — try again")

            result = DuelOperations.create_duel(
                inv["challenger"], username,
                problem["titleSlug"], problem["title"],
                problem["frontendQuestionId"], problem["difficulty"],
            )

            # Delete the invite so it can only be used once
            conn.execute("DELETE FROM duel_invites WHERE token = ?", [token])
            conn.commit()

            return {**result, "challengerName": inv["challenger"]}
        except Exception as e:
            error(f"accept_duel_invite failed: {e}")
            raise
        finally:
            conn.close()
