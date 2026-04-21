"""
AI-assisted learning routes — recap + code review for completed duels.
Powered by Gemini 2.5 Flash via google-genai, with SQLite caching.
"""

import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends

from auth import verify_api_key
from aws import DuelOperations
from db import get_db
from services import gemini_service
from background_tasks import fetch_problem_tags

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


def _user_context(duel: dict, username: str) -> str:
    """Build a short 'You won/lost' string from duel timing."""
    u = (username or "").lower()
    challenger = (duel.get("challenger") or "").lower()
    ch_time = duel.get("challenger_time") or -1
    cg_time = duel.get("challengee_time") or -1
    winner = (duel.get("winner") or "").lower()

    def fmt(ms: int) -> str:
        if ms is None or ms < 0:
            return "—"
        s = int(ms / 1000)
        return f"{s // 60}:{s % 60:02d}"

    my_time = ch_time if u == challenger else cg_time
    their_time = cg_time if u == challenger else ch_time

    if winner and winner == u:
        if their_time and their_time > 0 and my_time and my_time > 0:
            diff_s = max(0, int((their_time - my_time) / 1000))
            return f"You won in {fmt(my_time)} — {diff_s}s ahead."
        return f"You won in {fmt(my_time)}."
    if winner and winner != u and my_time and my_time > 0 and their_time and their_time > 0:
        diff_s = max(0, int((my_time - their_time) / 1000))
        return f"You lost by {diff_s}s — your time {fmt(my_time)}."
    if winner and winner != u:
        return "You did not finish in time."
    return f"Your time: {fmt(my_time)}."


def _load_cached_recap(slug: str) -> dict | None:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT pattern_name, takeaway, similar_problems, model_version, updated_at "
            "FROM ai_duel_recaps WHERE problem_slug = ?",
            [slug],
        ).fetchone()
        if not row:
            return None
        return {
            "pattern_name": row["pattern_name"],
            "takeaway": json.loads(row["takeaway"]) if row["takeaway"] else None,
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
                (problem_slug, pattern_name, takeaway, similar_problems, model_version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(problem_slug) DO UPDATE SET
                pattern_name = excluded.pattern_name,
                takeaway = excluded.takeaway,
                similar_problems = excluded.similar_problems,
                model_version = excluded.model_version,
                updated_at = excluded.updated_at
            """,
            [
                slug,
                recap.get("pattern_name"),
                json.dumps(recap.get("takeaway") or {}),
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


@router.post("/ai/duel-recap")
async def duel_recap_endpoint(
    request: dict,
    api_key: str = Depends(verify_api_key),
):
    """Return a Gemini-generated learning recap for a completed duel."""
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

        # Cache hit → skip rate limit and Gemini call entirely
        cached = _load_cached_recap(slug)
        if cached:
            cached["user_context"] = _user_context(duel, username)
            cached["problem"] = {"slug": slug, "title": title, "difficulty": difficulty}
            return {"success": True, "data": cached}

        if not gemini_service.allow_recap(username.lower()):
            return {"success": False, "error": "Rate limit exceeded — try again later"}

        tags = _load_cached_tags(slug)
        if tags is None:
            tags = fetch_problem_tags(slug)
            _save_tags(slug, tags)

        recap = gemini_service.generate_recap(slug, title, difficulty, tags)
        if not recap:
            return {"success": False, "error": "AI recap generation failed — please retry"}

        _save_recap(slug, recap)
        recap["user_context"] = _user_context(duel, username)
        recap["problem"] = {"slug": slug, "title": title, "difficulty": difficulty}
        recap["model_version"] = MODEL_VERSION
        return {"success": True, "data": recap}

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

        if not gemini_service.allow_review(username.lower()):
            return {"success": False, "error": "Rate limit exceeded — try again later"}

        review = gemini_service.review_code(slug, title, code, language)
        if not review:
            return {"success": False, "error": "AI code review failed — please retry"}

        return {"success": True, "data": review}

    except Exception as e:
        return {"success": False, "error": str(e)}
