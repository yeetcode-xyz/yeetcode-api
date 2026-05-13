"""
Billing routes — Stripe Checkout, Customer Portal, webhook, status.

Auth model: checkout/portal/status all require the shared API key (the website
proxies to these from server-side route handlers). The webhook endpoint is
public but verified via Stripe signature.
"""

from fastapi import APIRouter, Depends, Request, HTTPException

from auth import verify_api_key
from aws import UserOperations
from services import stripe_service
from logger import error, warning

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
