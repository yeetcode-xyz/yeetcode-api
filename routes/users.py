"""
User routes
"""

from fastapi import APIRouter, Depends
from typing import Dict
from pydantic import BaseModel

from models import UserData
from auth import verify_api_key
from aws import UserOperations
from discord_webhook import send_new_user_notification
from logger import error

router = APIRouter(tags=["Users"])

DEBUG_MODE = False

class CreateUserRequest(BaseModel):
    username: str
    email: str
    display_name: str = None
    university: str = None


class CreateGuestRequest(BaseModel):
    username: str
    display_name: str = None


@router.get("/user/{username}")
async def get_user_endpoint(
    username: str,
    api_key: str = Depends(verify_api_key)
):
    """Get user data"""
    try:
        user_data = UserOperations.get_user_data(username)
        if user_data:
            return {"success": True, "data": user_data}
        else:
            return {"success": False, "error": "User not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.put("/user/{username}")
async def update_user_endpoint(
    username: str,
    user_data: UserData,
    api_key: str = Depends(verify_api_key)
):
    """Update user data"""
    try:
        updates = {}
        if user_data.display_name is not None:
            updates['display_name'] = user_data.display_name
        if user_data.email is not None:
            updates['email'] = user_data.email.lower()
        if user_data.group_id is not None:
            updates['group_id'] = user_data.group_id

        success = UserOperations.update_user_data(username, updates)
        return {"success": success, "message": "User updated successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/user-data/{username}")
async def get_user_data_endpoint(
    username: str,
    api_key: str = Depends(verify_api_key)
):
    """Get user data"""
    try:
        user_data = UserOperations.get_user_data(username)
        if user_data:
            return {"success": True, "data": user_data}
        else:
            return {"success": False, "error": "User not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.put("/user-data/{username}")
async def update_user_data_endpoint(
    username: str,
    user_data: Dict,
    api_key: str = Depends(verify_api_key)
):
    """Update user data"""
    try:
        updates = {k: v for k, v in user_data.items() if k != 'username'}
        success = UserOperations.update_user_data(username, updates)
        return {"success": success}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/create-user-with-username")
async def create_user_with_username_endpoint(
    request: CreateUserRequest,
    api_key: str = Depends(verify_api_key)
):
    """Create a new user with specific username and email"""
    try:
        result = UserOperations.create_user_with_username(
            request.username, request.email, request.display_name, request.university
        )

        try:
            send_new_user_notification(request.username, request.email, request.display_name, request.university)
        except Exception as webhook_error:
            error(f"Discord webhook failed for user {request.username}: {webhook_error}")

        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/create-guest-user")
async def create_guest_user_endpoint(
    request: CreateGuestRequest,
    api_key: str = Depends(verify_api_key)
):
    """Create or resume a lightweight guest account keyed by LeetCode username."""
    try:
        result = UserOperations.create_guest_user(
            request.username, request.display_name
        )
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/award-xp")
async def award_xp_endpoint(
    request: dict,
    api_key: str = Depends(verify_api_key)
):
    """Award XP to a user"""
    try:
        username = request.get('username')
        xp_amount = request.get('xp_amount', 0)

        if not username or xp_amount <= 0:
            return {"success": False, "error": "Username and positive XP amount required"}

        success = UserOperations.award_xp(username, xp_amount)
        return {"success": success, "message": f"Awarded {xp_amount} XP to {username}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/leaderboard")
async def get_leaderboard_endpoint(
    api_key: str = Depends(verify_api_key)
):
    """Get leaderboard data"""
    try:
        result = UserOperations.get_leaderboard()
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/user-by-email/{email}")
async def get_user_by_email_endpoint(
    email: str,
    api_key: str = Depends(verify_api_key)
):
    """Get user data by email address"""
    try:
        result = UserOperations.get_user_by_email(email)
        if result:
            return {"success": True, "data": result}
        else:
            return {"success": False, "error": "User not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/group/{group_id}")
async def get_group_users_endpoint(
    group_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Get users in a specific group"""
    try:
        result = UserOperations.get_group_users(group_id)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}
