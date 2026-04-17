"""
Auth notifications for YeetCode via Discord webhook
"""

import os
import time
import requests
from typing import Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DISCORD_OTP_WEBHOOK_URL = os.getenv("DISCORD_OTP_WEBHOOK_URL")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"


def _post_discord(webhook_url: str, payload: dict):
    """POST a payload to a Discord webhook."""
    try:
        requests.post(webhook_url, json=payload, timeout=5)
    except Exception as e:
        if DEBUG_MODE:
            print(f"[ERROR] Discord webhook failed: {e}")


def send_email_otp(email: str, code: str) -> Dict:
    """Send OTP via Discord webhook."""
    if DEBUG_MODE:
        print(f"[DEBUG] OTP for {email}: {code}")

    webhook_url = DISCORD_OTP_WEBHOOK_URL or DISCORD_WEBHOOK_URL
    if not webhook_url:
        print(f"[WARN] No Discord webhook configured. OTP for {email}: {code}")
        return {"success": True, "messageId": f"console-{int(time.time())}"}

    payload = {
        "embeds": [
            {
                "title": "🔐 YeetCode Verification Code",
                "color": 0xFCD34D,
                "fields": [
                    {"name": "Email", "value": email, "inline": True},
                    {"name": "Code", "value": f"**`{code}`**", "inline": True},
                ],
                "footer": {"text": "Expires in 10 minutes"},
                "timestamp": None,
            }
        ]
    }
    _post_discord(webhook_url, payload)
    return {"success": True, "messageId": f"discord-{int(time.time())}"}


def send_duel_invite(email: str, challenger_name: str, difficulty: str, invite_url: str) -> Dict:
    """Send a duel invite notification via Discord webhook."""
    if DEBUG_MODE:
        print(f"[DEBUG] Duel invite for {email} from {challenger_name}")

    webhook_url = DISCORD_WEBHOOK_URL
    if not webhook_url:
        print(f"[WARN] No Discord webhook configured. Duel invite for {email} — {invite_url}")
        return {"success": True, "messageId": f"console-duel-{int(time.time())}"}

    diff_colors = {"easy": 0x16A34A, "medium": 0xD97706, "hard": 0xDC2626}
    color = diff_colors.get(difficulty.lower(), 0x2563EB)

    payload = {
        "embeds": [
            {
                "title": f"⚔️ {challenger_name} challenged you to a duel!",
                "color": color,
                "fields": [
                    {"name": "To", "value": email, "inline": True},
                    {"name": "Difficulty", "value": difficulty.capitalize(), "inline": True},
                    {"name": "Accept the Duel", "value": f"[Click here to join]({invite_url})", "inline": False},
                ],
                "footer": {"text": "Invite expires in 24 hours"},
            }
        ]
    }
    _post_discord(webhook_url, payload)
    return {"success": True, "messageId": f"discord-duel-{int(time.time())}"}