"""
Stripe service — Checkout sessions, customer portal, subscription provisioning.

Webhooks call into provision_from_event() to mutate user tier based on subscription
status. Checkout creates a Customer up-front when missing so we can attach the
yeetcode username via metadata + client_reference_id and look it up later.
"""

import os
from datetime import datetime, timezone
from typing import Optional, Dict

import stripe

from db import get_db
from logger import info, warning, error
from services.resend_service import send_subscription_welcome_email, send_cancellation_email


def _api_key() -> str:
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY is not set")
    return key


def _client():
    stripe.api_key = _api_key()
    return stripe


def _price_id() -> str:
    pid = os.getenv("STRIPE_PLUS_PRICE_ID")
    if not pid:
        raise RuntimeError("STRIPE_PLUS_PRICE_ID is not set")
    return pid


def _success_url() -> str:
    return os.getenv("BILLING_SUCCESS_URL") or "https://yeetcode.xyz/pricing/success?session_id={CHECKOUT_SESSION_ID}"


def _cancel_url() -> str:
    return os.getenv("BILLING_CANCEL_URL") or "https://yeetcode.xyz/pricing"


# ─── User <-> customer mapping ────────────────────────────────────────────────

def _get_user_row(username: str) -> Optional[Dict]:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", [username.lower()]
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _set_customer_id(username: str, customer_id: str):
    conn = get_db()
    try:
        conn.execute(
            "UPDATE users SET stripe_customer_id = ? WHERE username = ?",
            [customer_id, username.lower()],
        )
        conn.commit()
    finally:
        conn.close()


def _ensure_customer(username: str, email: Optional[str], display_name: Optional[str]) -> str:
    """Return the user's Stripe customer ID, creating one if missing."""
    user = _get_user_row(username)
    if not user:
        raise RuntimeError(f"User '{username}' not found")

    if user.get("stripe_customer_id"):
        return user["stripe_customer_id"]

    sc = _client()
    customer = sc.Customer.create(
        email=email or user.get("email"),
        name=display_name or user.get("display_name") or username,
        metadata={"username": username.lower()},
    )
    _set_customer_id(username, customer.id)
    return customer.id


# ─── Checkout / portal ────────────────────────────────────────────────────────

def create_checkout_session(username: str, email: Optional[str], display_name: Optional[str]) -> Dict:
    """Create a Stripe Checkout Session for the Plus subscription."""
    customer_id = _ensure_customer(username, email, display_name)
    sc = _client()

    session = sc.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        client_reference_id=username.lower(),
        line_items=[{"price": _price_id(), "quantity": 1}],
        success_url=_success_url(),
        cancel_url=_cancel_url(),
        allow_promotion_codes=True,
        subscription_data={"metadata": {"username": username.lower()}},
        metadata={"username": username.lower()},
    )
    return {"id": session.id, "url": session.url}


def create_portal_session(username: str, return_url: str) -> Dict:
    """Create a Stripe Customer Portal session so a user can manage their subscription."""
    user = _get_user_row(username)
    if not user or not user.get("stripe_customer_id"):
        raise RuntimeError("No Stripe customer for this user — subscribe first")

    sc = _client()
    session = sc.billing_portal.Session.create(
        customer=user["stripe_customer_id"],
        return_url=return_url,
    )
    return {"url": session.url}


# ─── Webhook event handling ───────────────────────────────────────────────────

def _is_event_processed(event_id: str) -> bool:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT 1 FROM subscription_events WHERE event_id = ?", [event_id]
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _record_event(event_id: str, type_: str):
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO subscription_events (event_id, type, received_at) VALUES (?, ?, ?)",
            [event_id, type_, datetime.now(timezone.utc).isoformat()],
        )
        conn.commit()
    finally:
        conn.close()


def _username_for_customer(customer_id: str) -> Optional[str]:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT username FROM users WHERE stripe_customer_id = ?", [customer_id]
        ).fetchone()
        return row["username"] if row else None
    finally:
        conn.close()


# Stripe statuses that mean the customer currently has access to paid features.
ACTIVE_STATUSES = {"active", "trialing", "past_due"}


def _apply_subscription(username: str, subscription: dict):
    """Persist the latest subscription state on the user row."""
    status = subscription.get("status")
    sub_id = subscription.get("id")
    period_end = subscription.get("current_period_end")  # unix ts (int)
    tier = "plus" if status in ACTIVE_STATUSES else "free"

    conn = get_db()
    try:
        conn.execute(
            """
            UPDATE users
               SET tier = ?,
                   stripe_subscription_id = ?,
                   subscription_status = ?,
                   subscription_current_period_end = ?
             WHERE username = ?
            """,
            [tier, sub_id, status, period_end, username.lower()],
        )
        conn.commit()
        info(f"[stripe] {username}: tier={tier} status={status} sub={sub_id}")
    finally:
        conn.close()


def construct_event(payload: bytes, signature: str) -> dict:
    """Verify and parse a webhook payload. Raises on invalid signature."""
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET is not set")
    sc = _client()
    return sc.Webhook.construct_event(payload, signature, secret)


def handle_event(event: dict) -> Dict:
    """Idempotently process a Stripe event. Returns {handled: bool, ...}."""
    event_id = event.get("id")
    type_ = event.get("type")
    if not event_id or not type_:
        return {"handled": False, "error": "Malformed event"}

    if _is_event_processed(event_id):
        return {"handled": True, "duplicate": True}

    obj = (event.get("data") or {}).get("object") or {}

    if type_ == "checkout.session.completed":
        username = (obj.get("client_reference_id") or "").lower() or (
            (obj.get("metadata") or {}).get("username") or ""
        ).lower()
        customer_id = obj.get("customer")
        sub_id = obj.get("subscription")

        if customer_id and username:
            _set_customer_id(username, customer_id)

        if sub_id:
            sc = _client()
            sub = sc.Subscription.retrieve(sub_id)
            target_user = username or _username_for_customer(customer_id or "")
            if target_user:
                _apply_subscription(target_user, sub)
                user_row = _get_user_row(target_user)
                send_subscription_welcome_email(
                    email=user_row.get("email") if user_row else None,
                    display_name=user_row.get("display_name") if user_row else None,
                )
            else:
                warning(f"[stripe] checkout.session.completed: no user for customer={customer_id}")

    elif type_ in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "customer.subscription.trial_will_end",
    }:
        customer_id = obj.get("customer")
        username = (obj.get("metadata") or {}).get("username") or _username_for_customer(customer_id or "")
        if not username:
            warning(f"[stripe] {type_}: no user mapping for customer={customer_id}")
        else:
            _apply_subscription(username, obj)
            if type_ == "customer.subscription.deleted":
                user_row = _get_user_row(username)
                send_cancellation_email(
                    email=user_row.get("email") if user_row else None,
                    display_name=user_row.get("display_name") if user_row else None,
                )

    elif type_ == "invoice.paid":
        customer_id = obj.get("customer")
        sub_id = obj.get("subscription")
        username = _username_for_customer(customer_id or "")
        if username and sub_id:
            sc = _client()
            sub = sc.Subscription.retrieve(sub_id)
            _apply_subscription(username, sub)

    elif type_ == "invoice.payment_failed":
        # Stripe also sends customer.subscription.updated with status=past_due,
        # which is what actually mutates the user row. Logging is enough here.
        info(f"[stripe] invoice.payment_failed for customer={obj.get('customer')}")

    else:
        # Other events are recorded but otherwise ignored.
        pass

    _record_event(event_id, type_)
    return {"handled": True, "type": type_}


# ─── Status helper ────────────────────────────────────────────────────────────

def get_status(username: str) -> Dict:
    user = _get_user_row(username)
    if not user:
        return {"tier": "free", "status": None}
    return {
        "tier": user.get("tier") or "free",
        "status": user.get("subscription_status"),
        "current_period_end": user.get("subscription_current_period_end"),
        "has_customer": bool(user.get("stripe_customer_id")),
    }
