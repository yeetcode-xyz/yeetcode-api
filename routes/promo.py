"""
Promo code routes — PAY404 (first 500 users get free Plus)
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends

from auth import verify_api_key
from db import get_db

router = APIRouter(tags=["Promo"])

# Active promo codes: code -> {max_uses, tier_grant, description}
PROMO_CODES = {
    "PAY404": {
        "max_uses": 500,
        "tier_grant": "plus",
        "description": "First 500 users get lifetime Plus",
    },
}


@router.post("/promo/redeem")
async def redeem_promo(
    request: dict,
    api_key: str = Depends(verify_api_key),
):
    """
    Redeem a promo code. Grants Plus tier if valid and not exhausted.
    Body: {username, code}
    """
    try:
        username = (request.get("username") or "").lower().strip()
        code = (request.get("code") or "").upper().strip()

        if not username or not code:
            return {"success": False, "error": "Username and code are required"}

        promo = PROMO_CODES.get(code)
        if not promo:
            return {"success": False, "error": "Invalid promo code"}

        conn = get_db()
        try:
            # Check if user already redeemed this code
            existing = conn.execute(
                "SELECT 1 FROM promo_redemptions WHERE username = ? AND code = ?",
                [username, code],
            ).fetchone()
            if existing:
                return {"success": False, "error": "You've already redeemed this code"}

            # Check total redemptions for this code
            count = conn.execute(
                "SELECT COUNT(*) FROM promo_redemptions WHERE code = ?", [code]
            ).fetchone()[0]
            if count >= promo["max_uses"]:
                return {
                    "success": False,
                    "error": f"This code has been fully redeemed ({promo['max_uses']}/{promo['max_uses']} used)",
                }

            # Check user exists
            user = conn.execute(
                "SELECT username, tier FROM users WHERE username = ?", [username]
            ).fetchone()
            if not user:
                return {"success": False, "error": "User not found"}

            # Already Plus?
            if user["tier"] == "plus":
                return {"success": False, "error": "You already have Plus!"}

            now_iso = datetime.now(timezone.utc).isoformat()

            # Record redemption
            conn.execute(
                "INSERT INTO promo_redemptions (username, code, redeemed_at) VALUES (?, ?, ?)",
                [username, code, now_iso],
            )

            # Grant Plus tier
            conn.execute(
                "UPDATE users SET tier = ? WHERE username = ?",
                [promo["tier_grant"], username],
            )
            conn.commit()

            remaining = promo["max_uses"] - count - 1

            return {
                "success": True,
                "data": {
                    "tier": promo["tier_grant"],
                    "message": f"Plus activated! You're #{count + 1} of {promo['max_uses']}.",
                    "remaining": remaining,
                },
            }
        finally:
            conn.close()
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/promo/status/{code}")
async def promo_status(
    code: str,
    api_key: str = Depends(verify_api_key),
):
    """Check how many redemptions a promo code has."""
    try:
        code = code.upper().strip()
        promo = PROMO_CODES.get(code)
        if not promo:
            return {"success": False, "error": "Invalid promo code"}

        conn = get_db()
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM promo_redemptions WHERE code = ?", [code]
            ).fetchone()[0]
            return {
                "success": True,
                "data": {
                    "code": code,
                    "used": count,
                    "max": promo["max_uses"],
                    "remaining": promo["max_uses"] - count,
                    "exhausted": count >= promo["max_uses"],
                },
            }
        finally:
            conn.close()
    except Exception as e:
        return {"success": False, "error": str(e)}
