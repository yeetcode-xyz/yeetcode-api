"""
Daily problem routes
"""

from fastapi import APIRouter, Depends

from models import DailyProblemRequest
from auth import verify_api_key
from aws import DailyProblemOperations

router = APIRouter(tags=["Daily Problems"])


@router.get("/daily-problem/{username}")
async def get_daily_problem_endpoint(
    username: str,
    api_key: str = Depends(verify_api_key)
):
    """Get daily problem data for a user"""
    try:
        result = DailyProblemOperations.get_daily_problem_data(username)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/complete-daily-problem")
async def complete_daily_problem_endpoint(
    request: DailyProblemRequest,
    api_key: str = Depends(verify_api_key)
):
    """Mark daily problem as completed for a user"""
    try:
        result = DailyProblemOperations.complete_daily_problem(request.username)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/top-daily-problems")
async def get_top_daily_problems_endpoint(
    api_key: str = Depends(verify_api_key)
):
    """Get top 2 daily problems"""
    try:
        result = DailyProblemOperations.get_top_daily_problems()
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/daily-completions")
async def get_daily_completions_endpoint(
    api_key: str = Depends(verify_api_key)
):
    """Get today's daily problem completions"""
    try:
        result = DailyProblemOperations.get_todays_completions()
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}
