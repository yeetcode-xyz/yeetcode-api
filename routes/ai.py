"""
AI-assisted learning routes — recap + timing coach + blitz coach + code review.
Powered by Gemini 2.5 Flash via google-genai, with SQLite caching.
"""

import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends

from auth import verify_api_key
from aws import DuelOperations
from db import get_db
from services import gemini_service, limits
from background_tasks import fetch_problem_tags

DAILY_QUOTA_MSG = "Daily AI insight limit reached — upgrade to Plus for unlimited insights"

router = APIRouter(tags=["AI"])

MAX_CODE_CHARS = 8000
MODEL_VERSION = "gemini-2.5-flash"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _participant_check(duel: dict, username: str) -> bool:
    u = (username or "").lower()
    return u in {
        (duel.get("challenger") or "").lower(),
        (duel.get("challengee") or "").lower(),
    }


def _fmt_time(ms: int | None) -> str:
    if ms is None or ms < 0:
        return "—"
    s = int(ms / 1000)
    return f"{s // 60}:{s % 60:02d}"


def _user_timing(duel: dict, username: str) -> dict:
    """Return my_time_ms, opponent_time_ms, outcome."""
    u = (username or "").lower()
    challenger = (duel.get("challenger") or "").lower()
    ch_time = duel.get("challenger_time") or -1
    cg_time = duel.get("challengee_time") or -1
    winner = (duel.get("winner") or "").lower()

    my_time = ch_time if u == challenger else cg_time
    their_time = cg_time if u == challenger else ch_time

    if winner == u:
        outcome = "won"
    elif winner and winner != u:
        outcome = "lost"
    elif my_time < 0:
        outcome = "dnf"
    else:
        outcome = "tied"
    return {"my_time_ms": my_time, "opponent_time_ms": their_time, "outcome": outcome}


def _user_context(duel: dict, username: str) -> str:
    """Build a short 'You won/lost' string from duel timing."""
    t = _user_timing(duel, username)
    my_time = t["my_time_ms"]
    their_time = t["opponent_time_ms"]
    outcome = t["outcome"]

    if outcome == "won":
        if their_time > 0 and my_time > 0:
            diff_s = max(0, int((their_time - my_time) / 1000))
            return f"You won in {_fmt_time(my_time)} — {diff_s}s ahead."
        return f"You won in {_fmt_time(my_time)}."
    if outcome == "lost":
        if my_time > 0 and their_time > 0:
            diff_s = max(0, int((my_time - their_time) / 1000))
            return f"You lost by {diff_s}s — your time {_fmt_time(my_time)}."
        return "You did not finish in time."
    return f"Your time: {_fmt_time(my_time)}."


# ─── Cache helpers ─────────────────────────────────────────────────────────────

def _load_cached_recap(slug: str) -> dict | None:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT pattern_name, takeaway, solve_strategy, similar_problems, model_version, updated_at "
            "FROM ai_duel_recaps WHERE problem_slug = ?",
            [slug],
        ).fetchone()
        if not row:
            return None
        # Reject legacy rows missing the new solve_strategy field — force regeneration.
        if not row["solve_strategy"]:
            return None
        return {
            "pattern_name": row["pattern_name"],
            "takeaway": json.loads(row["takeaway"]) if row["takeaway"] else None,
            "solve_strategy": json.loads(row["solve_strategy"]),
            "similar_problems": json.loads(row["similar_problems"]) if row["similar_problems"] else [],
            "model_version": row["model_version"],
            "updated_at": row["updated_at"],
        }
    finally:
        conn.close()


def _save_recap(slug: str, recap: dict):
    conn = get_db()
    try:
        now = _now_iso()
        conn.execute(
            """
            INSERT INTO ai_duel_recaps
                (problem_slug, pattern_name, takeaway, solve_strategy, similar_problems, model_version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(problem_slug) DO UPDATE SET
                pattern_name = excluded.pattern_name,
                takeaway = excluded.takeaway,
                solve_strategy = excluded.solve_strategy,
                similar_problems = excluded.similar_problems,
                model_version = excluded.model_version,
                updated_at = excluded.updated_at
            """,
            [
                slug,
                recap.get("pattern_name"),
                json.dumps(recap.get("takeaway") or {}),
                json.dumps(recap.get("solve_strategy") or {}),
                json.dumps(recap.get("similar_problems") or []),
                MODEL_VERSION,
                now,
                now,
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _load_cached_tags(slug: str) -> list[str] | None:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT tags FROM ai_problem_tags WHERE problem_slug = ?", [slug]
        ).fetchone()
        if not row or not row["tags"]:
            return None
        try:
            return json.loads(row["tags"])
        except Exception:
            return None
    finally:
        conn.close()


def _save_tags(slug: str, tags: list[str]):
    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO ai_problem_tags (problem_slug, tags, fetched_at)
            VALUES (?, ?, ?)
            ON CONFLICT(problem_slug) DO UPDATE SET
                tags = excluded.tags,
                fetched_at = excluded.fetched_at
            """,
            [slug, json.dumps(tags or []), _now_iso()],
        )
        conn.commit()
    finally:
        conn.close()


BUSY_MESSAGE = "Gemini is overloaded right now — please try again in a minute"


def _get_or_generate_recap(slug: str, title: str, difficulty: str, username: str) -> dict | None:
    """Cache-first recap lookup. Returns the recap dict or an error dict on failure."""
    cached = _load_cached_recap(slug)
    if cached:
        return cached

    allowed, _remaining = limits.check_ai_quota(username.lower())
    if not allowed:
        return {"__error__": DAILY_QUOTA_MSG}
    if not gemini_service.allow_recap(username.lower()):
        return {"__error__": "Rate limit exceeded — try again later"}

    tags = _load_cached_tags(slug)
    if tags is None:
        tags = fetch_problem_tags(slug)
        _save_tags(slug, tags)

    try:
        recap = gemini_service.generate_recap(slug, title, difficulty, tags)
    except gemini_service.GeminiBusyError:
        return {"__error__": BUSY_MESSAGE}
    if not recap:
        return None

    _save_recap(slug, recap)
    recap["model_version"] = MODEL_VERSION
    limits.record_ai_use(username.lower())
    return recap


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/ai/duel-recap")
async def duel_recap_endpoint(
    request: dict,
    api_key: str = Depends(verify_api_key),
):
    """Return a Gemini-generated learning recap for a completed duel. Fast path — cached per problem_slug."""
    try:
        duel_id = request.get("duel_id")
        username = request.get("username")
        if not duel_id or not username:
            return {"success": False, "error": "duel_id and username required"}

        duel_res = DuelOperations.get_duel_by_id(duel_id)
        if not duel_res.get("success"):
            return {"success": False, "error": duel_res.get("error") or "Duel not found"}
        duel = duel_res["data"]

        if not _participant_check(duel, username):
            return {"success": False, "error": "Not a participant of this duel"}
        if (duel.get("status") or "").upper() != "COMPLETED":
            return {"success": False, "error": "Duel is not completed"}

        slug = duel.get("problem_slug")
        title = duel.get("problem_title") or slug
        difficulty = duel.get("difficulty") or "Medium"
        if not slug:
            return {"success": False, "error": "Duel has no problem assigned"}

        recap = _get_or_generate_recap(slug, title, difficulty, username)
        if recap is None:
            return {"success": False, "error": "AI recap generation failed — please retry"}
        if isinstance(recap, dict) and recap.get("__error__"):
            return {"success": False, "error": recap["__error__"]}

        recap["user_context"] = _user_context(duel, username)
        recap["problem"] = {"slug": slug, "title": title, "difficulty": difficulty}
        return {"success": True, "data": recap}

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/ai/duel-timing-coach")
async def duel_timing_coach_endpoint(
    request: dict,
    api_key: str = Depends(verify_api_key),
):
    """Personal timing coach for a completed duel. Not cached — always calls Gemini."""
    try:
        duel_id = request.get("duel_id")
        username = request.get("username")
        if not duel_id or not username:
            return {"success": False, "error": "duel_id and username required"}

        duel_res = DuelOperations.get_duel_by_id(duel_id)
        if not duel_res.get("success"):
            return {"success": False, "error": duel_res.get("error") or "Duel not found"}
        duel = duel_res["data"]

        if not _participant_check(duel, username):
            return {"success": False, "error": "Not a participant of this duel"}
        if (duel.get("status") or "").upper() != "COMPLETED":
            return {"success": False, "error": "Duel is not completed"}

        slug = duel.get("problem_slug")
        title = duel.get("problem_title") or slug
        difficulty = duel.get("difficulty") or "Medium"
        if not slug:
            return {"success": False, "error": "Duel has no problem assigned"}

        timing = _user_timing(duel, username)
        if timing["my_time_ms"] <= 0 and timing["opponent_time_ms"] <= 0:
            return {"success": True, "data": None}

        allowed, _remaining = limits.check_ai_quota(username.lower())
        if not allowed:
            return {"success": False, "error": DAILY_QUOTA_MSG}
        if not gemini_service.allow_recap(username.lower()):
            return {"success": False, "error": "Rate limit exceeded — try again later"}

        cached = _load_cached_recap(slug)
        pattern_name = (cached or {}).get("pattern_name") or ""

        try:
            coach = gemini_service.generate_timing_coach(
                title=title,
                pattern_name=pattern_name,
                difficulty=difficulty,
                user_time_ms=timing["my_time_ms"],
                opponent_time_ms=timing["opponent_time_ms"],
                outcome=timing["outcome"],
            )
        except gemini_service.GeminiBusyError:
            return {"success": False, "error": BUSY_MESSAGE}

        if not coach:
            return {"success": False, "error": "AI timing coach failed — please retry"}

        limits.record_ai_use(username.lower())
        return {"success": True, "data": coach}

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/ai/problem-recap")
async def problem_recap_endpoint(
    request: dict,
    api_key: str = Depends(verify_api_key),
):
    """Cache-first recap for any LeetCode problem (no duel context).

    Used by daily problem, roadmap, etc. No participant check.
    """
    try:
        slug = request.get("slug")
        title = request.get("title") or slug
        difficulty = request.get("difficulty") or "Medium"
        username = request.get("username") or "anonymous"
        if not slug:
            return {"success": False, "error": "slug required"}

        recap = _get_or_generate_recap(slug, title, difficulty, username)
        if recap is None:
            return {"success": False, "error": "AI recap generation failed — please retry"}
        if isinstance(recap, dict) and recap.get("__error__"):
            return {"success": False, "error": recap["__error__"]}

        recap["problem"] = {"slug": slug, "title": title, "difficulty": difficulty}
        return {"success": True, "data": recap}

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/ai/blitz-coach")
async def blitz_coach_endpoint(
    request: dict,
    api_key: str = Depends(verify_api_key),
):
    """Given a Blitz run result, recommend the topic to drill + LeetCode problems."""
    try:
        username = request.get("username") or ""
        score = int(request.get("score") or 0)
        total = int(request.get("total") or 0)
        wrong_topics = request.get("wrong_topics") or []
        if not username:
            return {"success": False, "error": "username required"}
        if total <= 0:
            return {"success": False, "error": "total must be > 0"}

        allowed, _remaining = limits.check_ai_quota(username.lower())
        if not allowed:
            return {"success": False, "error": DAILY_QUOTA_MSG}
        if not gemini_service.allow_recap(username.lower()):
            return {"success": False, "error": "Rate limit exceeded — try again later"}

        try:
            coach = gemini_service.generate_blitz_coach(score, total, wrong_topics)
        except gemini_service.GeminiBusyError:
            return {"success": False, "error": BUSY_MESSAGE}
        if not coach:
            return {"success": False, "error": "AI coach generation failed — please retry"}

        limits.record_ai_use(username.lower())
        return {"success": True, "data": coach}

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/ai/code-review")
async def code_review_endpoint(
    request: dict,
    api_key: str = Depends(verify_api_key),
):
    """Return a Gemini-generated critique of user-submitted code. Not cached."""
    try:
        duel_id = request.get("duel_id")
        username = request.get("username")
        code = request.get("code") or ""
        language = request.get("language") or "python"

        if not duel_id or not username:
            return {"success": False, "error": "duel_id and username required"}
        if not code.strip():
            return {"success": False, "error": "code is required"}
        if len(code) > MAX_CODE_CHARS:
            return {"success": False, "error": f"Code too long (max {MAX_CODE_CHARS} chars)"}

        duel_res = DuelOperations.get_duel_by_id(duel_id)
        if not duel_res.get("success"):
            return {"success": False, "error": duel_res.get("error") or "Duel not found"}
        duel = duel_res["data"]

        if not _participant_check(duel, username):
            return {"success": False, "error": "Not a participant of this duel"}

        slug = duel.get("problem_slug")
        title = duel.get("problem_title") or slug
        if not slug:
            return {"success": False, "error": "Duel has no problem assigned"}

        allowed, _remaining = limits.check_ai_quota(username.lower())
        if not allowed:
            return {"success": False, "error": DAILY_QUOTA_MSG}
        if not gemini_service.allow_review(username.lower()):
            return {"success": False, "error": "Rate limit exceeded — try again later"}

        try:
            review = gemini_service.review_code(slug, title, code, language)
        except gemini_service.GeminiBusyError:
            return {"success": False, "error": BUSY_MESSAGE}
        if not review:
            return {"success": False, "error": "AI code review failed — please retry"}

        limits.record_ai_use(username.lower())
        return {"success": True, "data": review}

    except Exception as e:
        return {"success": False, "error": str(e)}
