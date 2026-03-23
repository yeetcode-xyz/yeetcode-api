"""
Duel routes
"""

import asyncio
from fastapi import APIRouter, Depends

from models import DuelRequest
from auth import verify_api_key
from aws import DuelOperations

router = APIRouter(tags=["Duels"])


def _normalize_duel(duel: dict) -> dict:
    """Normalize duel fields for a consistent API response."""
    d = dict(duel)
    # is_wager: SQLite stores 0/1 integer, coerce to bool
    if 'is_wager' in d:
        d['is_wager'] = bool(d['is_wager'])
    # wager_amount: derive from challenger_wager so frontend has a single field
    if not d.get('wager_amount'):
        d['wager_amount'] = d.get('challenger_wager') or d.get('challengee_wager') or 0
    return d


@router.get("/duels/{username}")
async def get_user_duels_endpoint(
    username: str,
    api_key: str = Depends(verify_api_key)
):
    """Get duels for a user"""
    try:
        result = DuelOperations.get_user_duels(username)
        if result.get('success') and result.get('data'):
            result['data'] = [
                _normalize_duel(d) for d in result['data']
                if d.get('problem_slug') and d.get('problem_slug') != 'None'
            ]
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/create-duel")
async def create_duel_endpoint(
    request: DuelRequest,
    api_key: str = Depends(verify_api_key)
):
    """Create a new duel"""
    try:
        problem_slug   = request.problem_slug
        problem_title  = request.problem_title
        problem_number = request.problem_number
        difficulty     = request.difficulty

        # Auto-assign a random problem if the frontend didn't specify one
        if not problem_slug:
            from background_tasks import fetch_random_problem
            problem = await asyncio.to_thread(fetch_random_problem)
            if not problem:
                return {"success": False, "error": "Could not find a suitable problem — try again"}
            problem_slug   = problem["titleSlug"]
            problem_title  = problem["title"]
            problem_number = problem["frontendQuestionId"]
            difficulty     = problem["difficulty"]

        result = DuelOperations.create_duel(
            request.username,
            request.opponent,
            problem_slug,
            problem_title,
            problem_number,
            difficulty,
            request.is_wager or False,
            request.wager_amount
        )
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/accept-duel")
async def accept_duel_endpoint(
    request: DuelRequest,
    api_key: str = Depends(verify_api_key)
):
    """Accept a duel"""
    try:
        result = DuelOperations.accept_duel(
            request.username,
            request.duel_id,
            request.wager_amount
        )
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/start-duel")
async def start_duel_endpoint(
    request: DuelRequest,
    api_key: str = Depends(verify_api_key)
):
    """Mark that a user has started working on a duel"""
    try:
        result = DuelOperations.start_duel(request.username, request.duel_id)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/complete-duel")
async def complete_duel_endpoint(
    request: DuelRequest,
    api_key: str = Depends(verify_api_key)
):
    """Complete a duel submission (legacy endpoint)"""
    try:
        result = DuelOperations.record_duel_submission(request.username, request.duel_id, 0)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/reject-duel")
async def reject_duel_endpoint(
    request: dict,
    api_key: str = Depends(verify_api_key)
):
    """Reject a duel"""
    try:
        duel_id = request.get('duel_id') or request.get('duelId')
        if not duel_id:
            return {"success": False, "error": "Duel ID required"}
        result = DuelOperations.reject_duel(duel_id)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/record-duel-submission")
async def record_duel_submission_endpoint(
    request: dict,
    api_key: str = Depends(verify_api_key)
):
    """Record a duel submission with elapsed time"""
    try:
        username   = request.get('username')
        duel_id    = request.get('duel_id')
        elapsed_ms = request.get('elapsed_ms', 0)

        if not duel_id or not username:
            return {"success": False, "error": "Duel ID and username required"}

        result = DuelOperations.record_duel_submission(username, duel_id, elapsed_ms)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/verify-duel-solve")
async def verify_duel_solve_endpoint(
    request: dict,
    api_key: str = Depends(verify_api_key)
):
    """
    Triggered when user clicks 'Verify Solve'.
    Immediately checks LeetCode for an accepted submission,
    then records the time if found.
    Returns { found: bool, elapsed_ms?, completed?, winner?, xpAwarded? }
    """
    try:
        username = request.get('username')
        duel_id  = request.get('duel_id')

        if not duel_id or not username:
            return {"success": False, "error": "Duel ID and username required"}

        from db import get_db
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM duels WHERE duel_id = ?", [duel_id]
            ).fetchone()
        finally:
            conn.close()

        if not row:
            return {"success": False, "error": "Duel not found"}

        duel = dict(row)
        problem_slug = duel.get("problem_slug")
        if not problem_slug:
            return {"success": False, "error": "Duel has no problem assigned"}

        norm_user = username.lower()
        is_challenger = norm_user == duel.get("challenger")
        if not is_challenger and norm_user != duel.get("challengee"):
            return {"success": False, "error": "User not part of this duel"}

        start_field = "challenger_start_time" if is_challenger else "challengee_start_time"
        start_iso   = duel.get(start_field)
        if not start_iso:
            return {"success": False, "found": False, "error": "Duel not started yet"}

        from background_tasks import check_duel_solve
        elapsed_ms = await asyncio.to_thread(check_duel_solve, username, problem_slug, start_iso)

        if elapsed_ms is None:
            return {"success": True, "found": False}

        result = DuelOperations.record_duel_submission(username, duel_id, elapsed_ms)
        return {
            "success":    True,
            "found":      True,
            "elapsed_ms": elapsed_ms,
            **result,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/duel/{duel_id}")
async def get_duel_endpoint(
    duel_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Get a specific duel by ID"""
    try:
        result = DuelOperations.get_duel_by_id(duel_id)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}
