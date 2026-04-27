"""
Frontend challenge routes — HTML/CSS/JS coding challenges
"""

import json
from collections import defaultdict
from datetime import datetime, timezone
from fastapi import APIRouter, Depends

from auth import verify_api_key
from aws import UserOperations
from db import get_db

router = APIRouter(tags=["Frontend Challenges"])

XP_BY_DIFFICULTY = {"easy": 100, "medium": 300, "hard": 500}


def _row_to_dict(row):
    return dict(row) if row else None


@router.get("/frontend/challenges")
async def list_challenges(
    category: str = None,
    type: str = None,
    difficulty: str = None,
    api_key: str = Depends(verify_api_key),
):
    """List all frontend challenges (metadata only, no code)."""
    conn = get_db()
    try:
        query = "SELECT id, challenge_id, title, category, type, difficulty FROM frontend_challenges WHERE 1=1"
        params = []
        if category:
            query += " AND category = ?"
            params.append(category)
        if type:
            query += " AND type = ?"
            params.append(type)
        if difficulty:
            query += " AND difficulty = ?"
            params.append(difficulty.lower())
        query += " ORDER BY id"

        rows = conn.execute(query, params).fetchall()
        challenges = [dict(r) for r in rows]

        # Group by category
        by_cat = defaultdict(list)
        for c in challenges:
            by_cat[c["category"]].append(c)
        categories = [{"name": cat, "challenges": items} for cat, items in by_cat.items()]

        return {"success": True, "data": {"total": len(challenges), "categories": categories}}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


@router.get("/frontend/challenges/{challenge_id}")
async def get_challenge(
    challenge_id: str,
    api_key: str = Depends(verify_api_key),
):
    """Get a single challenge with starter code and test cases."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM frontend_challenges WHERE challenge_id = ?",
            [challenge_id],
        ).fetchone()
        if not row:
            return {"success": False, "error": "Challenge not found"}

        challenge = dict(row)
        # Parse JSON fields
        challenge["test_cases"] = json.loads(challenge.get("test_cases") or "[]")
        challenge["hints"] = json.loads(challenge.get("hints") or "[]")
        return {"success": True, "data": challenge}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


@router.post("/frontend/submit")
async def submit_solution(
    request: dict,
    api_key: str = Depends(verify_api_key),
):
    """
    Submit a frontend challenge solution.
    Body: {username, challenge_id, html, css, js, tests_passed, tests_total, time_ms}
    Awards XP on first solve.
    """
    try:
        username = request.get("username", "").lower()
        challenge_id = request.get("challenge_id", "")
        html = request.get("html", "")
        css = request.get("css", "")
        js = request.get("js", "")
        tests_passed = int(request.get("tests_passed", 0))
        tests_total = int(request.get("tests_total", 0))
        time_ms = int(request.get("time_ms", 0))

        if not username or not challenge_id:
            return {"success": False, "error": "username and challenge_id are required"}

        solved = 1 if tests_passed == tests_total and tests_total > 0 else 0
        now_iso = datetime.now(timezone.utc).isoformat()

        conn = get_db()
        try:
            # Check if already solved
            is_first_solve = False
            xp_awarded = 0

            if solved:
                existing = conn.execute(
                    "SELECT id FROM frontend_submissions WHERE username = ? AND challenge_id = ? AND solved = 1",
                    [username, challenge_id],
                ).fetchone()
                if not existing:
                    is_first_solve = True
                    # Get difficulty for XP
                    challenge_row = conn.execute(
                        "SELECT difficulty FROM frontend_challenges WHERE challenge_id = ?",
                        [challenge_id],
                    ).fetchone()
                    if challenge_row:
                        diff = challenge_row["difficulty"].lower()
                        xp_awarded = XP_BY_DIFFICULTY.get(diff, 100)

            conn.execute(
                """INSERT INTO frontend_submissions
                   (username, challenge_id, html, css, js, tests_passed, tests_total,
                    solved, time_ms, xp_awarded, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                [username, challenge_id, html, css, js, tests_passed, tests_total,
                 solved, time_ms, xp_awarded, now_iso],
            )
            conn.commit()

            # Award XP
            if is_first_solve and xp_awarded > 0:
                UserOperations.award_xp(username, xp_awarded)

            return {
                "success": True,
                "data": {
                    "solved": bool(solved),
                    "xp_awarded": xp_awarded,
                    "is_first_solve": is_first_solve,
                    "tests_passed": tests_passed,
                    "tests_total": tests_total,
                },
            }
        finally:
            conn.close()
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/frontend/progress/{username}")
async def get_progress(
    username: str,
    api_key: str = Depends(verify_api_key),
):
    """Get a user's frontend challenge progress."""
    norm_user = username.lower()
    conn = get_db()
    try:
        # Get all solved challenge IDs
        solved_rows = conn.execute(
            "SELECT DISTINCT challenge_id FROM frontend_submissions WHERE username = ? AND solved = 1",
            [norm_user],
        ).fetchall()
        solved_ids = [r["challenge_id"] for r in solved_rows]

        # Get total challenges per category
        all_rows = conn.execute(
            "SELECT challenge_id, category, difficulty FROM frontend_challenges ORDER BY id"
        ).fetchall()

        per_category = defaultdict(lambda: {"solved": 0, "total": 0})
        for r in all_rows:
            cat = r["category"]
            per_category[cat]["total"] += 1
            if r["challenge_id"] in solved_ids:
                per_category[cat]["solved"] += 1

        # Total XP from frontend challenges
        xp_row = conn.execute(
            "SELECT COALESCE(SUM(xp_awarded), 0) as total_xp FROM frontend_submissions WHERE username = ? AND solved = 1",
            [norm_user],
        ).fetchone()

        return {
            "success": True,
            "data": {
                "solved": solved_ids,
                "per_category": dict(per_category),
                "total_xp": xp_row["total_xp"] if xp_row else 0,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()
