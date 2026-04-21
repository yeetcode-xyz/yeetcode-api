"""
Blitz mode routes — fast MCQ/fill-in-blank challenges
"""

import json
import random
import secrets
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from auth import verify_api_key
from db import get_db

router = APIRouter(tags=["Blitz"])


@router.get("/blitz/questions")
async def get_blitz_questions(
    count: int = 50,
    api_key: str = Depends(verify_api_key),
):
    """Return N random blitz questions (default 50 for timed mode)."""
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM blitz_questions").fetchall()
        questions = [dict(r) for r in rows]
        sample = random.sample(questions, min(count, len(questions)))
        for q in sample:
            q["options"] = json.loads(q["options"])
        return {"success": True, "data": sample}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


@router.post("/blitz/challenge")
async def create_blitz_challenge(
    request: dict,
    api_key: str = Depends(verify_api_key),
):
    """Create a shareable blitz challenge with a fixed question set and time limit."""
    challenger = request.get("username")
    time_limit_ms = request.get("time_limit_ms", 60000)
    if not challenger:
        return {"success": False, "error": "username required"}

    conn = get_db()
    try:
        rows = conn.execute("SELECT id FROM blitz_questions").fetchall()
        all_ids = [r["id"] for r in rows]
        selected = random.sample(all_ids, min(50, len(all_ids)))

        token = secrets.token_urlsafe(10)
        now_iso = datetime.now(timezone.utc).isoformat()
        expires_at = int(time.time()) + 86400  # 24 hours

        conn.execute(
            """INSERT INTO blitz_challenges (token, challenger, question_ids, time_limit_ms, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [token, challenger.lower(), json.dumps(selected), time_limit_ms, now_iso, expires_at],
        )
        conn.commit()
        return {
            "success": True,
            "data": {
                "token": token,
                "invite_url": f"https://yeetcode.xyz/blitz-challenge/{token}",
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


@router.get("/blitz/challenge/{token}")
async def get_blitz_challenge(
    token: str,
    api_key: str = Depends(verify_api_key),
):
    """Get the questions for a blitz challenge."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM blitz_challenges WHERE token = ?", [token]
        ).fetchone()
        if not row:
            return {"success": False, "error": "Challenge not found"}
        inv = dict(row)
        if int(time.time()) > inv["expires_at"]:
            return {"success": False, "error": "Challenge has expired"}

        ids = json.loads(inv["question_ids"])
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT * FROM blitz_questions WHERE id IN ({placeholders})", ids
        ).fetchall()
        id_to_q = {r["id"]: dict(r) for r in rows}
        questions = []
        for qid in ids:
            if qid in id_to_q:
                q = id_to_q[qid]
                q["options"] = json.loads(q["options"])
                questions.append(q)

        return {
            "success": True,
            "data": {
                "token": token,
                "challenger": inv["challenger"],
                "time_limit_ms": inv.get("time_limit_ms", 60000),
                "questions": questions,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


@router.post("/blitz/score")
async def submit_blitz_score(
    request: dict,
    api_key: str = Depends(verify_api_key),
):
    """Submit a blitz score."""
    username = request.get("username")
    score = request.get("score")
    total = request.get("total")
    time_ms = request.get("time_ms")
    challenge_token = request.get("challenge_token")

    if not username or score is None or total is None or time_ms is None:
        return {"success": False, "error": "username, score, total, time_ms required"}

    conn = get_db()
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO blitz_scores (username, challenge_token, score, total, time_ms, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [username.lower(), challenge_token, score, total, time_ms, now_iso],
        )
        conn.commit()

        # Personal best
        best = conn.execute(
            """SELECT score, total, time_ms FROM blitz_scores
               WHERE username = ?
               ORDER BY score DESC, CAST(score AS REAL) / total DESC, time_ms ASC LIMIT 1""",
            [username.lower()],
        ).fetchone()

        return {
            "success": True,
            "data": {
                "personal_best": dict(best) if best else None,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


@router.get("/blitz/personal-best/{username}")
async def get_personal_best(
    username: str,
    api_key: str = Depends(verify_api_key),
):
    """Return the personal best score for a user."""
    conn = get_db()
    try:
        best = conn.execute(
            """SELECT score, total, time_ms FROM blitz_scores
               WHERE username = ?
               ORDER BY score DESC, CAST(score AS REAL) / total DESC, time_ms ASC LIMIT 1""",
            [username.lower()],
        ).fetchone()
        return {"success": True, "data": dict(best) if best else None}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


@router.get("/blitz/leaderboard")
async def get_blitz_leaderboard(
    api_key: str = Depends(verify_api_key),
):
    """Top blitz scores (best score, fastest time per user)."""
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT b.username, u.display_name,
                      MAX(b.score) as best_score,
                      b.total,
                      MIN(CASE WHEN b.score = (SELECT MAX(score) FROM blitz_scores WHERE username = b.username)
                               THEN b.time_ms END) as best_time
               FROM blitz_scores b
               LEFT JOIN users u ON u.username = b.username
               GROUP BY b.username
               ORDER BY best_score DESC, CAST(best_score AS REAL) / b.total DESC, best_time ASC
               LIMIT 20""",
        ).fetchall()
        return {"success": True, "data": [dict(r) for r in rows]}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()
