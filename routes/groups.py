"""
Group routes
"""

from fastapi import APIRouter, Depends

from models import GroupRequest, JoinGroupRequest
from auth import verify_api_key
from aws import GroupOperations, UserOperations

router = APIRouter(tags=["Groups"])


@router.post("/create-group")
async def create_group_endpoint(
    request: GroupRequest,
    api_key: str = Depends(verify_api_key)
):
    """Create a new group and assign user as group leader"""
    try:
        result = GroupOperations.create_group(request.username, request.display_name)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/join-group")
async def join_group_endpoint(
    request: JoinGroupRequest,
    api_key: str = Depends(verify_api_key)
):
    """Join an existing group using invite code"""
    try:
        result = GroupOperations.join_group(
            request.username,
            request.invite_code,
            request.display_name
        )
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/leave-group")
async def leave_group_endpoint(
    request: GroupRequest,
    api_key: str = Depends(verify_api_key)
):
    """Leave the current group"""
    try:
        result = GroupOperations.leave_group(request.username)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/group-stats/{group_id}")
async def get_group_stats_endpoint(
    group_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Get leaderboard stats for a group"""
    try:
        result = GroupOperations.get_group_stats(group_id)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/all-groups")
async def get_all_groups_endpoint(
    api_key: str = Depends(verify_api_key)
):
    """Get all groups"""
    try:
        result = GroupOperations.get_all_groups()
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/group/{group_id}")
async def get_group_endpoint(
    group_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Get specific group by ID"""
    try:
        result = GroupOperations.get_group_by_id(group_id)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.put("/update-display-name")
async def update_display_name_endpoint(
    request: GroupRequest,
    api_key: str = Depends(verify_api_key)
):
    """Update user's display name"""
    try:
        if not request.display_name or not request.display_name.strip():
            return {"success": False, "error": "No display name provided"}

        updates = {'display_name': request.display_name}
        success = UserOperations.update_user_data(request.username, updates)
        return {"success": success}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/university-leaderboard")
async def get_university_leaderboard_endpoint(
    api_key: str = Depends(verify_api_key)
):
    """Get university leaderboard with aggregated stats"""
    try:
        result = UserOperations.get_all_users_for_university_leaderboard()
        if not result.get("success"):
            return result

        university_stats = {}
        for user in result.get("data", []):
            university = user.get("university")
            if not university or university in ("undefined", "", "Other"):
                continue

            if university not in university_stats:
                university_stats[university] = {
                    "university": university,
                    "students": 0,
                    "easy": 0,
                    "medium": 0,
                    "hard": 0,
                    "total": 0,
                    "total_xp": 0,
                    "top_student": None,
                    "top_student_xp": 0
                }

            stats = university_stats[university]
            stats["students"] += 1

            try:
                easy   = int(user.get("easy",   0) or 0)
                medium = int(user.get("medium", 0) or 0)
                hard   = int(user.get("hard",   0) or 0)
                bonus  = int(user.get("xp",     0) or 0)
            except (ValueError, TypeError):
                easy = medium = hard = bonus = 0

            stats["easy"]   += easy
            stats["medium"] += medium
            stats["hard"]   += hard
            stats["total"]  += easy + medium + hard

            user_xp = easy * 100 + medium * 300 + hard * 500 + bonus
            stats["total_xp"] += user_xp

            if user_xp > stats["top_student_xp"]:
                stats["top_student_xp"] = user_xp
                stats["top_student"] = user.get("username", "Unknown")

        leaderboard = sorted(university_stats.values(), key=lambda x: x["total_xp"], reverse=True)
        return {"success": True, "data": leaderboard}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/my-university-leaderboard/{username}")
async def get_my_university_leaderboard_endpoint(
    username: str,
    api_key: str = Depends(verify_api_key)
):
    """Get individual student rankings for the user's university"""
    try:
        user_data = UserOperations.get_user_data(username)
        if not user_data:
            return {"success": False, "error": "User not found"}

        user_university = user_data.get("university")
        if not user_university or user_university in ("undefined", "", "Other"):
            return {"success": False, "error": "User not enrolled in a university"}

        result = UserOperations.get_all_users_for_university_leaderboard()
        if not result.get("success"):
            return result

        university_users = []
        for user in result.get("data", []):
            if user.get("university") != user_university:
                continue

            try:
                easy   = int(user.get("easy",   0) or 0)
                medium = int(user.get("medium", 0) or 0)
                hard   = int(user.get("hard",   0) or 0)
                bonus  = int(user.get("xp",     0) or 0)
            except (ValueError, TypeError):
                easy = medium = hard = bonus = 0

            total_xp = easy * 100 + medium * 300 + hard * 500 + bonus

            university_users.append({
                "username":     user.get("username", ""),
                "display_name": user.get("display_name", user.get("username", "")),
                "easy":         easy,
                "medium":       medium,
                "hard":         hard,
                "xp":           bonus,
                "total_xp":     total_xp,
            })

        university_users.sort(key=lambda x: x["total_xp"], reverse=True)

        return {
            "success": True,
            "data": university_users,
            "university": user_university,
            "total_students": len(university_users)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
