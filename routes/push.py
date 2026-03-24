"""Push notification subscription endpoints."""

import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from auth import verify_api_key
from db import get_db

router = APIRouter(tags=["Push"])


@router.get("/push/vapid-public-key")
async def get_vapid_public_key():
    """Return the VAPID public key for the browser to use when subscribing."""
    return {"publicKey": os.getenv("VAPID_PUBLIC_KEY", "")}


@router.post("/push/subscribe")
async def subscribe(
    request: dict,
    api_key: str = Depends(verify_api_key),
):
    """Save a push subscription for a user."""
    username = request.get("username")
    endpoint = request.get("endpoint")
    p256dh   = request.get("p256dh")
    auth     = request.get("auth")

    if not all([username, endpoint, p256dh, auth]):
        return {"success": False, "error": "Missing required fields"}

    conn = get_db()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO push_subscriptions
                (username, endpoint, p256dh, auth, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [username.lower(), endpoint, p256dh, auth,
             datetime.now(timezone.utc).isoformat()],
        )
        conn.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


@router.delete("/push/subscribe")
async def unsubscribe(
    request: dict,
    api_key: str = Depends(verify_api_key),
):
    """Remove a push subscription."""
    endpoint = request.get("endpoint")
    username = request.get("username")

    conn = get_db()
    try:
        if endpoint:
            conn.execute(
                "DELETE FROM push_subscriptions WHERE endpoint = ?", [endpoint]
            )
        elif username:
            conn.execute(
                "DELETE FROM push_subscriptions WHERE username = ?",
                [username.lower()],
            )
        conn.commit()
        return {"success": True}
    finally:
        conn.close()
