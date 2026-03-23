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
            problem = await asyncio.to_thread(fetch_random_problem, difficulty or "EASY")
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
