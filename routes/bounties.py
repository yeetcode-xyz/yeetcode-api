from fastapi import APIRouter, Depends

from models import BountyRequest
from auth import verify_api_key
from aws import BountyOperations

router = APIRouter(tags=["Bounties"])


@router.get("/bounties/{username}")
async def get_user_bounties_endpoint(
    username: str,
    api_key: str = Depends(verify_api_key),
):
    """Get bounties for a user"""
    try:
        result = BountyOperations.get_user_bounties(username)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/all-bounties")
async def get_all_bounties_endpoint(
    api_key: str = Depends(verify_api_key)
):
    """Get all bounties"""
    try:
        result = BountyOperations.get_all_bounties()
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/bounty/{bounty_id}")
async def get_bounty_endpoint(
    bounty_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Get specific bounty by ID"""
    try:
        result = BountyOperations.get_bounty_by_id(bounty_id)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/bounty-progress/{bounty_id}")
async def get_bounty_progress_endpoint(
    bounty_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Get progress for a specific bounty"""
    try:
        result = BountyOperations.get_bounty_progress(bounty_id)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/refresh-bounty-cache")
async def refresh_bounty_cache_endpoint(
    api_key: str = Depends(verify_api_key)
):
    """No-op: SQLite is always up-to-date, no cache to refresh"""
    return {"success": True, "message": "No cache to refresh — SQLite is always current"}
