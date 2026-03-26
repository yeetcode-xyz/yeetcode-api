"""
Friends routes
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from auth import verify_api_key
from db import get_db

router = APIRouter(tags=["Friends"])


class FriendRequestBody(BaseModel):
    requester: str
    addressee: str


class RemoveFriendBody(BaseModel):
    username: str
    friend: str


@router.get("/friends/{username}")
async def get_friends(username: str, api_key: str = Depends(verify_api_key)):
    """Get accepted friends for a user"""
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT
                CASE WHEN f.requester = ? THEN f.addressee ELSE f.requester END AS friend_username,
                COALESCE(u.display_name, CASE WHEN f.requester = ? THEN f.addressee ELSE f.requester END) AS display_name,
                f.created_at
            FROM friendships f
            LEFT JOIN users u ON u.username = CASE WHEN f.requester = ? THEN f.addressee ELSE f.requester END
            WHERE (f.requester = ? OR f.addressee = ?) AND f.status = 'accepted'
        """, (username, username, username, username, username)).fetchall()
        conn.close()
        friends = [{"username": row["friend_username"], "display_name": row["display_name"], "created_at": row["created_at"]} for row in rows]
        return {"success": True, "data": friends}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/friends/{username}/pending")
async def get_pending_requests(username: str, api_key: str = Depends(verify_api_key)):
    """Get pending friend requests received by a user"""
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT f.requester, COALESCE(u.display_name, f.requester) AS display_name, f.created_at
            FROM friendships f
            LEFT JOIN users u ON u.username = f.requester
            WHERE f.addressee = ? AND f.status = 'pending'
        """, (username,)).fetchall()
        conn.close()
        requests = [{"requester": row["requester"], "display_name": row["display_name"], "created_at": row["created_at"]} for row in rows]
        return {"success": True, "data": requests}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/friends/request")
async def send_friend_request(body: FriendRequestBody, api_key: str = Depends(verify_api_key)):
    """Send a friend request"""
    requester = body.requester.lower().strip()
    addressee = body.addressee.lower().strip()

    if not requester or not addressee:
        return {"success": False, "error": "requester and addressee required"}
    if requester == addressee:
        return {"success": False, "error": "Cannot add yourself"}

    try:
        conn = get_db()

        # Check if addressee exists
        user = conn.execute("SELECT username FROM users WHERE username = ?", (addressee,)).fetchone()
        if not user:
            conn.close()
            return {"success": False, "error": "User not found"}

        # Check existing relationship (either direction)
        existing = conn.execute("""
            SELECT requester, addressee, status FROM friendships
            WHERE (requester = ? AND addressee = ?) OR (requester = ? AND addressee = ?)
        """, (requester, addressee, addressee, requester)).fetchone()

        if existing:
            if existing["status"] == "accepted":
                conn.close()
                return {"success": False, "error": "Already friends"}
            # If the other person already sent a request to us, auto-accept
            if existing["status"] == "pending" and existing["requester"] == addressee:
                conn.execute("""
                    UPDATE friendships SET status = 'accepted' WHERE requester = ? AND addressee = ?
                """, (addressee, requester))
                conn.commit()
                conn.close()
                return {"success": True, "auto_accepted": True}
            # We already sent a request
            conn.close()
            return {"success": False, "error": "Friend request already sent"}

        conn.execute("""
            INSERT INTO friendships (requester, addressee, status, created_at)
            VALUES (?, ?, 'pending', ?)
        """, (requester, addressee, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/friends/accept")
async def accept_friend_request(body: FriendRequestBody, api_key: str = Depends(verify_api_key)):
    """Accept a friend request"""
    requester = body.requester.lower().strip()
    addressee = body.addressee.lower().strip()

    try:
        conn = get_db()
        conn.execute("""
            UPDATE friendships SET status = 'accepted'
            WHERE requester = ? AND addressee = ? AND status = 'pending'
        """, (requester, addressee))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/friends/decline")
async def decline_friend_request(body: FriendRequestBody, api_key: str = Depends(verify_api_key)):
    """Decline a friend request"""
    requester = body.requester.lower().strip()
    addressee = body.addressee.lower().strip()

    try:
        conn = get_db()
        conn.execute("""
            DELETE FROM friendships WHERE requester = ? AND addressee = ? AND status = 'pending'
        """, (requester, addressee))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/friends/remove")
async def remove_friend(body: RemoveFriendBody, api_key: str = Depends(verify_api_key)):
    """Remove a friend (both directions)"""
    username = body.username.lower().strip()
    friend = body.friend.lower().strip()

    try:
        conn = get_db()
        conn.execute("""
            DELETE FROM friendships
            WHERE (requester = ? AND addressee = ?) OR (requester = ? AND addressee = ?)
        """, (username, friend, friend, username))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
