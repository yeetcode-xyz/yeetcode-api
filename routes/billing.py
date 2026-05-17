"""
Billing routes — Stripe Checkout, Customer Portal, webhook, status.

Auth model: checkout/portal/status all require the shared API key (the website
proxies to these from server-side route handlers). The webhook endpoint is
public but verified via Stripe signature.
"""

import os
import hmac
import hashlib
import time

from fastapi import APIRouter, Depends, Request, HTTPException

from auth import verify_api_key
from aws import UserOperations
from db import get_db
from services import stripe_service
from logger import error, info, warning

router = APIRouter(tags=["Billing"])


@router.post("/billing/checkout")
async def create_checkout(
    request: dict,
    api_key: str = Depends(verify_api_key),
):
    """Create a Stripe Checkout session for the Plus subscription."""
    username = (request.get("username") or "").lower()
    if not username:
        return {"success": False, "error": "username required"}

    user = UserOperations.get_user_data(username)
    if not user:
        return {"success": False, "error": "User not found"}
    if user.get("is_guest"):
        return {"success": False, "error": "Sign up before subscribing"}

    try:
        session = stripe_service.create_checkout_session(
            username=username,
            email=user.get("email"),
            display_name=user.get("display_name"),
        )
        return {"success": True, "data": session}
    except Exception as e:
        error(f"create_checkout failed for {username}: {e}")
        return {"success": False, "error": str(e)}


@router.post("/billing/portal")
async def create_portal(
    request: dict,
    api_key: str = Depends(verify_api_key),
):
    """Create a Stripe Customer Portal session for managing the subscription."""
    username = (request.get("username") or "").lower()
    return_url = request.get("return_url") or "https://yeetcode.xyz/dashboard"
    if not username:
        return {"success": False, "error": "username required"}
    try:
        session = stripe_service.create_portal_session(username, return_url)
        return {"success": True, "data": session}
    except Exception as e:
        error(f"create_portal failed for {username}: {e}")
        return {"success": False, "error": str(e)}


@router.get("/billing/status/{username}")
async def billing_status(
    username: str,
    api_key: str = Depends(verify_api_key),
):
    """Return tier + subscription status for a user."""
    try:
        return {"success": True, "data": stripe_service.get_status(username)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/billing/webhook")
async def stripe_webhook(request: Request):
    """Receive Stripe webhooks. Verifies signature, then mutates user tier."""
    payload = await request.body()
    signature = request.headers.get("stripe-signature") or ""
    try:
        event = stripe_service.construct_event(payload, signature)
    except Exception as e:
        warning(f"[stripe] invalid webhook signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        result = stripe_service.handle_event(event)
        return {"success": True, **result}
    except Exception as e:
        error(f"[stripe] webhook handler failed: {e}")
        # Return 500 so Stripe retries.
        raise HTTPException(status_code=500, detail="Webhook handler error")


def _verify_resend_signature(payload: bytes, headers: dict) -> bool:
    """Verify Resend webhook signature (Svix-based signing).

    Resend signs webhooks with HMAC-SHA256 over "svix-id.svix-timestamp.body".
    Returns False (rather than raising) so the endpoint can 400 cleanly.
    """
    secret = os.getenv("RESEND_WEBHOOK_SECRET", "")
    if not secret:
        warning("[resend-webhook] RESEND_WEBHOOK_SECRET not set — skipping verification")
        return True  # fail open in dev; set the secret in prod

    svix_id        = headers.get("svix-id", "")
    svix_timestamp = headers.get("svix-timestamp", "")
    svix_signature = headers.get("svix-signature", "")

    if not svix_id or not svix_timestamp or not svix_signature:
        return False

    # Reject timestamps older than 5 minutes to prevent replay attacks
    try:
        if abs(time.time() - int(svix_timestamp)) > 300:
            return False
    except ValueError:
        return False

    signed_content = f"{svix_id}.{svix_timestamp}.{payload.decode()}"
    # Secret may be prefixed with "whsec_"; strip it before base64-decoding
    raw_secret = secret.removeprefix("whsec_")
    import base64
    key = base64.b64decode(raw_secret)
    expected = base64.b64encode(
        hmac.new(key, signed_content.encode(), hashlib.sha256).digest()
    ).decode()

    for sig in svix_signature.split(" "):
        if sig.startswith("v1,") and hmac.compare_digest(sig[3:], expected):
            return True
    return False


@router.post("/webhooks/resend")
async def resend_webhook(request: Request):
    """Receive Resend contact webhooks and sync unsubscribe state to the DB.

    Wire up contact.updated, contact.created, contact.deleted in the Resend dashboard.
    Endpoint is public but signature-verified via RESEND_WEBHOOK_SECRET.
    """
    payload = await request.body()
    if not _verify_resend_signature(payload, dict(request.headers)):
        warning("[resend-webhook] invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        import json
        event = json.loads(payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = event.get("type", "")
    data = event.get("data", {})
    email = data.get("email", "").lower()

    if not email:
        return {"success": True}

    if event_type == "contact.updated":
        unsubscribed = data.get("unsubscribed", False)
        conn = get_db()
        try:
            conn.execute(
                "UPDATE users SET marketing_unsubscribed = ? WHERE email = ?",
                (1 if unsubscribed else 0, email),
            )
            conn.commit()
            info(f"[resend-webhook] {email} marketing_unsubscribed={unsubscribed}")
        finally:
            conn.close()

    elif event_type == "contact.deleted":
        conn = get_db()
        try:
            conn.execute(
                "UPDATE users SET marketing_unsubscribed = 1 WHERE email = ?",
                (email,),
            )
            conn.commit()
            info(f"[resend-webhook] {email} deleted from audience → marked unsubscribed")
        finally:
            conn.close()

    return {"success": True}
