"""
Web Push notification service using VAPID (pywebpush).

VAPID key generation (run once, save to .env):
    python3 -c "
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
import base64
key = ec.generate_private_key(ec.SECP256R1())
priv = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()).decode()
pub = base64.urlsafe_b64encode(key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)).rstrip(b'=').decode()
print('VAPID_PRIVATE_KEY=' + repr(priv))
print('VAPID_PUBLIC_KEY=' + pub)
"
"""

import os
import json
import logging

log = logging.getLogger(__name__)

VAPID_PUBLIC_KEY  = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_EMAIL       = os.getenv("VAPID_CLAIMS_EMAIL", "admin@yeetcode.xyz")

def _fix_pem_key(raw: str) -> str:
    """Reconstruct a valid PEM from a mangled single-line or \\n-escaped key."""
    raw = raw.replace("\\n", "\n").strip()
    if "\n" in raw:
        return raw  # already has real newlines
    # Spaces replaced newlines — extract base64 body and reformat
    b64 = (
        raw.replace("-----BEGIN EC PRIVATE KEY-----", "")
           .replace("-----END EC PRIVATE KEY-----", "")
           .replace(" ", "")
    )
    lines = [b64[i:i+64] for i in range(0, len(b64), 64)]
    return "-----BEGIN EC PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END EC PRIVATE KEY-----\n"

_raw_key = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_PRIVATE_KEY = _fix_pem_key(_raw_key) if _raw_key else ""


def send_push(username: str, title: str, body: str, url: str = "/") -> int:
    """
    Send a push notification to all subscriptions for a user.
    Returns the number of notifications sent. Never raises.
    """
    if not VAPID_PRIVATE_KEY:
        return 0

    from db import get_db
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        log.warning("pywebpush not installed — push notifications disabled")
        return 0

    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE username = ?",
            [username.lower()],
        ).fetchall()
    finally:
        conn.close()

    sent  = 0
    stale = []

    for row in rows:
        try:
            webpush(
                subscription_info={
                    "endpoint": row["endpoint"],
                    "keys": {"p256dh": row["p256dh"], "auth": row["auth"]},
                },
                data=json.dumps({"title": title, "body": body, "url": url}),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{VAPID_EMAIL}"},
            )
            sent += 1
        except WebPushException as e:
            resp = getattr(e, "response", None)
            if resp is not None and resp.status_code in (404, 410):
                stale.append(row["endpoint"])
            else:
                log.warning(f"Push failed for {username}: {e}")
        except Exception as e:
            log.warning(f"Push error for {username}: {e}")

    if stale:
        conn = get_db()
        try:
            for endpoint in stale:
                conn.execute(
                    "DELETE FROM push_subscriptions WHERE endpoint = ?", [endpoint]
                )
            conn.commit()
        finally:
            conn.close()

    return sent
