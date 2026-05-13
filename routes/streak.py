"""
Streak freeze routes — let users protect a missed day.

Free tier: 1 freeze / month. Plus tier: 3 freezes / month.
Balance is reset on the first call of each calendar month based on user.tier.
"""

from fastapi import APIRouter, Depends

from auth import verify_api_key
from services import limits

router = APIRouter(tags=["Streak"])


@router.get("/streak/status/{username}")
async def streak_status(
    username: str,
    api_key: str = Depends(verify_api_key),
):
    """Return current freeze balance + tier allowance."""
    try:
        return {"success": True, "data": limits.freeze_status(username)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/streak/freeze")
async def use_streak_freeze(
    request: dict,
    api_key: str = Depends(verify_api_key),
):
    """Consume one freeze for a missed past date.

    Body: {username, date: "YYYY-MM-DD"}
    """
    username = (request.get("username") or "").lower()
    date_str = request.get("date") or ""
    if not username or not date_str:
        return {"success": False, "error": "username and date required"}
    try:
        result = limits.consume_streak_freeze(username, date_str)
        if not result.get("success"):
            return {"success": False, "error": result.get("error")}
        return {"success": True, "data": {"remaining": result["remaining"]}}
    except Exception as e:
        return {"success": False, "error": str(e)}
