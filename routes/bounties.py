from fastapi import APIRouter, Depends, Query

from auth import verify_api_key
from aws import BountyOperations

router = APIRouter(tags=["Bounties"])


@router.get("/bounties/{username}")
async def get_user_bounties_endpoint(
    username: str,
    api_key: str = Depends(verify_api_key),
):
    """Get active bounties for a user with progress, tags, completedAt, completedByCount."""
    try:
        return BountyOperations.get_user_bounties(username)
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/bounty-feed")
async def get_bounty_feed_endpoint(
    limit: int = Query(default=20, ge=1, le=100),
    api_key: str = Depends(verify_api_key),
):
    """Recent bounty completions across all users."""
    try:
        return BountyOperations.get_bounty_feed(limit=limit)
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/bounty/{bounty_id}/leaderboard")
async def get_bounty_leaderboard_endpoint(
    bounty_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    api_key: str = Depends(verify_api_key),
):
    """Top users by progress for a specific bounty."""
    try:
        return BountyOperations.get_bounty_leaderboard(bounty_id, limit=limit)
    except Exception as e:
        return {"success": False, "error": str(e)}
