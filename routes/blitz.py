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
    challenger     = request.get("username")
    time_limit_ms  = request.get("time_limit_ms", 60000)
    opponent       = request.get("opponent_username")          # direct challenge (new flow)
    challenger_score   = request.get("challenger_score", 0)   # submitted later via /submit
    challenger_total   = request.get("challenger_total", 0)
    challenger_time_ms = request.get("challenger_time_ms", 0)

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
            """INSERT INTO blitz_challenges
               (token, challenger, question_ids, time_limit_ms, created_at, expires_at,
                challenger_score, challenger_total, challenger_time_ms, opponent, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [token, challenger.lower(), json.dumps(selected), time_limit_ms, now_iso, expires_at,
             challenger_score, challenger_total, challenger_time_ms,
             opponent.lower() if opponent else None, "pending"],
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
                "challenger_score":    inv.get("challenger_score", 0),
                "challenger_total":    inv.get("challenger_total", 0),
                "challenger_time_ms":  inv.get("challenger_time_ms", 0),
                "questions": questions,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


@router.get("/blitz/challenge/{token}/results")
async def get_challenge_results(
    token: str,
    api_key: str = Depends(verify_api_key),
):
    """Return both players' scores for a challenge so a winner can be shown."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM blitz_challenges WHERE token = ?", [token]
        ).fetchone()
        if not row:
            return {"success": False, "error": "Challenge not found"}
        inv = dict(row)

        challenger_name = inv["challenger"]
        c_score   = inv.get("challenger_score", 0) or 0
        c_total   = inv.get("challenger_total", 0) or 0
        c_time_ms = inv.get("challenger_time_ms", 0) or 0

        # Opponent = anyone who submitted a score for this token that isn't the challenger
        opp_row = conn.execute(
            """SELECT username, score, total, time_ms FROM blitz_scores
               WHERE challenge_token = ? AND username != ?
               ORDER BY score DESC, CAST(score AS REAL) / CASE WHEN total > 0 THEN total ELSE 1 END DESC, time_ms ASC
               LIMIT 1""",
            [token, challenger_name],
        ).fetchone()

        opponent = dict(opp_row) if opp_row else None

        # Determine winner if both have played
        winner = None
        if opponent and c_total > 0:
            o_score   = opponent["score"]
            o_total   = opponent["total"]
            o_time_ms = opponent["time_ms"]
            if c_score != o_score:
                winner = challenger_name if c_score > o_score else opponent["username"]
            else:
                c_acc = c_score / c_total if c_total else 0
                o_acc = o_score / o_total if o_total else 0
                if c_acc != o_acc:
                    winner = challenger_name if c_acc > o_acc else opponent["username"]
                else:
                    winner = challenger_name if c_time_ms <= o_time_ms else opponent["username"]

        return {
            "success": True,
            "data": {
                "challenger": {
                    "username":  challenger_name,
                    "score":     c_score,
                    "total":     c_total,
                    "time_ms":   c_time_ms,
                    "has_played": c_total > 0,
                },
                "opponent": opponent,
                "winner": winner,
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


# ── XP helper ────────────────────────────────────────────────────────────────
def _award_xp(conn, username: str, amount: int):
    conn.execute(
        "UPDATE users SET xp = xp + ? WHERE username = ?",
        [amount, username.lower()],
    )


def _finish_challenge(conn, token: str, inv: dict):
    """Called when both players have submitted scores. Determines winner, awards XP."""
    c_score = inv.get("challenger_score") or 0
    c_total = inv.get("challenger_total") or 0
    c_time  = inv.get("challenger_time_ms") or 0
    o_score = inv.get("opponent_score") or 0
    o_total = inv.get("opponent_total") or 0
    o_time  = inv.get("opponent_time_ms") or 0

    # Determine winner
    if c_score != o_score:
        winner = inv["challenger"] if c_score > o_score else inv["opponent"]
    else:
        c_acc = c_score / c_total if c_total else 0
        o_acc = o_score / o_total if o_total else 0
        if c_acc != o_acc:
            winner = inv["challenger"] if c_acc > o_acc else inv["opponent"]
        elif c_time != o_time:
            winner = inv["challenger"] if c_time < o_time else inv["opponent"]
        else:
            winner = "tie"

    # Award XP
    if winner == "tie":
        _award_xp(conn, inv["challenger"], 5)
        _award_xp(conn, inv["opponent"], 5)
        c_xp = o_xp = 5
    else:
        loser = inv["opponent"] if winner == inv["challenger"] else inv["challenger"]
        _award_xp(conn, winner, 10)
        _award_xp(conn, loser, 3)
        c_xp = 10 if winner == inv["challenger"] else 3
        o_xp = 10 if winner == inv["opponent"]   else 3

    conn.execute(
        """UPDATE blitz_challenges
           SET status = 'completed', winner = ?, xp_awarded = 1
           WHERE token = ?""",
        [winner, token],
    )
    return winner, c_xp, o_xp


# ── List users to challenge ───────────────────────────────────────────────────
@router.get("/blitz/opponents/{username}")
async def get_blitz_opponents(
    username: str,
    api_key: str = Depends(verify_api_key),
):
    """Returns recent challengers first, then group/global leaderboard."""
    conn = get_db()
    try:
        me = username.lower()

        # Recent: distinct opponents from this user's challenges (last 20)
        recent_rows = conn.execute(
            """SELECT CASE WHEN LOWER(challenger) = ? THEN opponent ELSE challenger END AS other_user,
                      MAX(created_at) AS last_at
               FROM blitz_challenges
               WHERE (LOWER(challenger) = ? OR LOWER(opponent) = ?)
                 AND opponent IS NOT NULL
               GROUP BY other_user
               ORDER BY last_at DESC
               LIMIT 10""",
            [me, me, me],
        ).fetchall()
        recent_usernames = [r["other_user"].lower() for r in recent_rows]

        # Get user details for recent challengers
        recent_details = {}
        if recent_usernames:
            ph = ",".join("?" * len(recent_usernames))
            rows = conn.execute(
                f"SELECT username, display_name, xp FROM users WHERE LOWER(username) IN ({ph})",
                recent_usernames,
            ).fetchall()
            for r in rows:
                recent_details[r["username"].lower()] = dict(r)

        recent = [
            {**recent_details.get(u, {"username": u, "display_name": u, "xp": 0}), "recent": True}
            for u in recent_usernames
        ]

        # Group/global leaderboard (exclude self and already-included recents)
        exclude = {me} | set(recent_usernames)
        ph2 = ",".join("?" * len(exclude))
        leaderboard = conn.execute(
            f"""SELECT username, display_name, xp
                FROM users
                WHERE LOWER(username) NOT IN ({ph2}) AND is_guest = 0
                ORDER BY xp DESC
                LIMIT 30""",
            list(exclude),
        ).fetchall()

        return {
            "success": True,
            "data": {
                "recent": recent,
                "leaderboard": [dict(r) for r in leaderboard],
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


# ── Pending challenges for a user ─────────────────────────────────────────────
@router.get("/blitz/challenges/pending/{username}")
async def get_pending_challenges(
    username: str,
    api_key: str = Depends(verify_api_key),
):
    """All pending challenges where this user is the opponent (not yet played)."""
    conn = get_db()
    try:
        me = username.lower()
        rows = conn.execute(
            """SELECT token, challenger, time_limit_ms, challenger_score, challenger_total, created_at
               FROM blitz_challenges
               WHERE LOWER(opponent) = ? AND status = 'pending'
                 AND challenger_total > 0
               ORDER BY created_at DESC
               LIMIT 20""",
            [me],
        ).fetchall()
        challenges = []
        for r in rows:
            row = dict(r)
            # Enrich with challenger display name
            u = conn.execute(
                "SELECT display_name FROM users WHERE LOWER(username) = ?",
                [row["challenger"].lower()],
            ).fetchone()
            row["challenger_display"] = (u["display_name"] if u else None) or row["challenger"]
            challenges.append(row)

        return {"success": True, "data": {"challenges": challenges, "count": len(challenges)}}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


# ── Submit score for one side of a challenge ──────────────────────────────────
@router.post("/blitz/challenge/{token}/submit")
async def submit_challenge_score(
    token: str,
    request: dict,
    api_key: str = Depends(verify_api_key),
):
    """Submit a player's score for a specific challenge. Auto-completes when both sides done."""
    username = request.get("username", "").lower()
    score    = request.get("score", 0)
    total    = request.get("total", 0)
    time_ms  = request.get("time_ms", 0)

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM blitz_challenges WHERE token = ?", [token]
        ).fetchone()
        if not row:
            return {"success": False, "error": "Challenge not found"}
        inv = dict(row)

        is_challenger = inv["challenger"].lower() == username
        is_opponent   = inv.get("opponent", "").lower() == username if inv.get("opponent") else False

        if not is_challenger and not is_opponent:
            return {"success": False, "error": "You are not part of this challenge"}

        if is_challenger:
            conn.execute(
                """UPDATE blitz_challenges
                   SET challenger_score = ?, challenger_total = ?, challenger_time_ms = ?
                   WHERE token = ?""",
                [score, total, time_ms, token],
            )
            inv["challenger_score"]    = score
            inv["challenger_total"]    = total
            inv["challenger_time_ms"]  = time_ms
        else:
            conn.execute(
                """UPDATE blitz_challenges
                   SET opponent_score = ?, opponent_total = ?, opponent_time_ms = ?
                   WHERE token = ?""",
                [score, total, time_ms, token],
            )
            inv["opponent_score"]   = score
            inv["opponent_total"]   = total
            inv["opponent_time_ms"] = time_ms

        conn.commit()

        # Finish challenge if both sides have played
        winner = None
        my_xp  = 0
        if (inv.get("challenger_total") or 0) > 0 and (inv.get("opponent_total") or 0) > 0 \
                and not inv.get("xp_awarded"):
            winner, c_xp, o_xp = _finish_challenge(conn, token, inv)
            my_xp = c_xp if is_challenger else o_xp
            conn.commit()

        return {"success": True, "data": {"winner": winner, "xp_earned": my_xp}}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()
