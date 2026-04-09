"""
Email operations for YeetCode using Resend
"""

import os
import time
import requests
from typing import Dict
import resend
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Resend
resend.api_key = os.getenv("RESEND_API_KEY")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"


def _discord_fallback(content: str):
    """Post to Discord webhook when Resend is not configured."""
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=5)
    except Exception:
        pass


def send_email_otp(email: str, code: str) -> Dict:
    """Send OTP email using Resend"""
    try:
        if not resend.api_key:
            _discord_fallback(f"📧 **[NO RESEND — pretend this is an email]**\n**To:** {email}\n**Subject:** Your YeetCode Verification Code\n**Code:** `{code}`")
            return {"success": True, "messageId": f"mock-id-{int(time.time())}"}

        if DEBUG_MODE:
            print(f"[DEBUG] Sending email to {email} with code {code}")

        response = resend.Emails.send({
            "from": "YeetCode <auth@yeetcode.xyz>",
            "to": [email],
            "subject": "Your YeetCode Verification Code",
            "html": f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <h1 style="color: #1a1a1a; font-size: 28px; margin: 0;">🚀 YeetCode</h1>
                        <p style="color: #666; font-size: 16px; margin: 10px 0 0 0;">Competitive LeetCode Platform</p>
                    </div>
                    
                    <div style="background: #f8f9fa; border: 2px solid #000; border-radius: 12px; padding: 30px; text-align: center;">
                        <h2 style="color: #1a1a1a; font-size: 24px; margin: 0 0 20px 0;">Your Verification Code</h2>
                        
                        <div style="background: #fff; border: 3px solid #000; border-radius: 8px; padding: 20px; margin: 20px 0; font-family: 'Courier New', monospace;">
                            <div style="font-size: 36px; font-weight: bold; color: #2563eb; letter-spacing: 8px;">{code}</div>
                        </div>
                        
                        <p style="color: #374151; font-size: 16px; margin: 20px 0 10px 0;">
                            Enter this code in your YeetCode app to continue setting up your account.
                        </p>
                        
                        <p style="color: #6b7280; font-size: 14px; margin: 10px 0;">
                            This code will expire in 10 minutes.
                        </p>
                    </div>
                    
                    <div style="text-align: center; margin-top: 30px; color: #9ca3af; font-size: 12px;">
                        <p>If you didn't request this verification code, you can safely ignore this email.</p>
                        <p>© 2025 YeetCode. Ready to compete?</p>
                    </div>
                </div>
            """
        })
        
        if DEBUG_MODE:
            print(f"[DEBUG] Email sent successfully: {response.get('id')}")
        return {"success": True, "messageId": response.get("id")}
        
    except Exception as error:
        if DEBUG_MODE:
            print(f"[ERROR] Failed to send email: {error}")
        raise Exception(f"Failed to send email: {str(error)}")


def send_duel_invite(email: str, challenger_name: str, difficulty: str, invite_url: str) -> Dict:
    """Send a duel invite email to someone (may or may not have a YeetCode account)."""
    try:
        if not resend.api_key:
            _discord_fallback(f"📧 **[NO RESEND — pretend this is an email]**\n**To:** {email}\n**Subject:** ⚔️ {challenger_name} wants to duel you on YeetCode!\n**Difficulty:** {difficulty}\n**Invite URL:** {invite_url}")
            return {"success": True, "messageId": f"mock-duel-{int(time.time())}"}

        diff_colors = {"Easy": "#16a34a", "Medium": "#d97706", "Hard": "#dc2626"}
        color = diff_colors.get(difficulty.capitalize(), "#2563eb")

        response = resend.Emails.send({
            "from": "YeetCode <duels@yeetcode.xyz>",
            "to": [email],
            "subject": f"⚔️ {challenger_name} wants to duel you on YeetCode!",
            "html": f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <h1 style="color: #1a1a1a; font-size: 28px; margin: 0;">⚔️ YeetCode</h1>
                        <p style="color: #666; font-size: 16px; margin: 10px 0 0 0;">Competitive LeetCode Platform</p>
                    </div>

                    <div style="background: #eff6ff; border: 2px solid #3b82f6; border-radius: 12px; padding: 30px; text-align: center;">
                        <h2 style="color: #1a1a1a; font-size: 22px; margin: 0 0 12px 0;">
                            {challenger_name} challenged you to a duel!
                        </h2>
                        <p style="color: #374151; font-size: 16px; margin: 0 0 20px 0;">
                            Difficulty: <span style="color: {color}; font-weight: bold;">{difficulty.capitalize()}</span>
                        </p>
                        <a href="{invite_url}" style="display: inline-block; background: #2563eb; color: white; font-weight: bold; font-size: 16px; padding: 14px 32px; border-radius: 8px; text-decoration: none; border: 3px solid #1d4ed8;">
                            ⚔️ Accept the Duel
                        </a>
                        <p style="color: #6b7280; font-size: 13px; margin: 20px 0 0 0;">
                            Already have an account? Just click and log in.<br>
                            New to YeetCode? Create a free account — it only takes 30 seconds.
                        </p>
                    </div>

                    <div style="background: #f9fafb; border-radius: 8px; padding: 16px; margin-top: 20px;">
                        <p style="color: #374151; font-size: 14px; margin: 0 0 8px 0; font-weight: bold;">What is YeetCode?</p>
                        <p style="color: #6b7280; font-size: 13px; margin: 0;">
                            YeetCode is a competitive LeetCode platform where you race friends to solve coding problems. Track your streak, earn XP, and climb the leaderboard.
                        </p>
                    </div>

                    <div style="text-align: center; margin-top: 24px; color: #9ca3af; font-size: 12px;">
                        <p>This invite expires in 24 hours.</p>
                        <p>© 2025 YeetCode. Ready to compete?</p>
                    </div>
                </div>
            """
        })

        return {"success": True, "messageId": response.get("id")}

    except Exception as error:
        if DEBUG_MODE:
            print(f"[ERROR] Failed to send duel invite: {error}")
        raise Exception(f"Failed to send duel invite: {str(error)}")