"""
Resend-backed email senders.

Currently used for: subscription welcome email when a user upgrades to Plus.
Add new callsites for any other transactional email that should go via SMTP
(receipts go via Stripe automatically and don't need to live here).
"""

import os
from typing import Optional

import resend

from logger import info, warning, error

FROM_ADDRESS = os.getenv("RESEND_FROM", "hello@yeetcode.xyz")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://yeetcode.xyz/dashboard")


def _configured() -> bool:
    key = os.getenv("RESEND_API_KEY")
    if not key or key.startswith("your_"):
        return False
    resend.api_key = key
    return True


def send_subscription_welcome_email(
    email: Optional[str],
    display_name: Optional[str],
) -> bool:
    """Fire-and-forget welcome email for a fresh Plus subscriber.

    Returns True on send success, False otherwise. Does NOT raise — the
    webhook handler must always 200 to Stripe regardless of email outcome.
    """
    if not email:
        warning("[resend] welcome email skipped: no email")
        return False

    if not _configured():
        warning("[resend] welcome email skipped: RESEND_API_KEY not set")
        return False

    name = display_name or "grinder"
    subject = "You're in. Welcome to YeetCode Plus."

    html = f"""\
<!DOCTYPE html>
<html>
  <body style="margin:0;padding:0;background:#facc15;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#0a0a0a;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#facc15;padding:40px 20px;">
      <tr>
        <td align="center">
          <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border:3px solid #000;border-radius:16px;box-shadow:6px 6px 0 #000;">
            <tr>
              <td style="padding:36px 32px 8px 32px;">
                <div style="display:inline-block;background:#000;color:#facc15;font-weight:800;font-size:11px;letter-spacing:3px;text-transform:uppercase;padding:6px 14px;border-radius:999px;">
                  Plus unlocked
                </div>
              </td>
            </tr>
            <tr>
              <td style="padding:8px 32px 0 32px;">
                <h1 style="margin:0;font-size:40px;line-height:1.05;font-weight:800;letter-spacing:-0.02em;">
                  Welcome,<br/>{name}.
                </h1>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 32px 0 32px;">
                <p style="margin:0;font-size:16px;line-height:1.5;color:#404040;font-weight:500;">
                  Your YeetCode Plus subscription is live. Every limit just turned into <b>unlimited</b>.
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:24px 32px 0 32px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:separate;border-spacing:8px;">
                  <tr>
                    <td style="background:#dcfce7;border:2px solid #4ade80;border-radius:12px;padding:12px;width:50%;">
                      <p style="margin:0;font-size:10px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;color:#52525b;">AI insights</p>
                      <p style="margin:2px 0 0 0;font-size:14px;font-weight:800;">Unlimited</p>
                    </td>
                    <td style="background:#dbeafe;border:2px solid #60a5fa;border-radius:12px;padding:12px;width:50%;">
                      <p style="margin:0;font-size:10px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;color:#52525b;">Frontend challenges</p>
                      <p style="margin:2px 0 0 0;font-size:14px;font-weight:800;">Unlimited</p>
                    </td>
                  </tr>
                  <tr>
                    <td style="background:#f3e8ff;border:2px solid #c084fc;border-radius:12px;padding:12px;">
                      <p style="margin:0;font-size:10px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;color:#52525b;">Company problems</p>
                      <p style="margin:2px 0 0 0;font-size:14px;font-weight:800;">Unlimited</p>
                    </td>
                    <td style="background:#ffedd5;border:2px solid #fb923c;border-radius:12px;padding:12px;">
                      <p style="margin:0;font-size:10px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;color:#52525b;">Roadmap tracking</p>
                      <p style="margin:2px 0 0 0;font-size:14px;font-weight:800;">Enabled</p>
                    </td>
                  </tr>
                  <tr>
                    <td style="background:#cffafe;border:2px solid #22d3ee;border-radius:12px;padding:12px;">
                      <p style="margin:0;font-size:10px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;color:#52525b;">Streak freezes</p>
                      <p style="margin:2px 0 0 0;font-size:14px;font-weight:800;">3 / month</p>
                    </td>
                    <td style="background:#fef9c3;border:2px solid #facc15;border-radius:12px;padding:12px;">
                      <p style="margin:0;font-size:10px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;color:#52525b;">Cancel anytime</p>
                      <p style="margin:2px 0 0 0;font-size:14px;font-weight:800;">From the dashboard</p>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:28px 32px 32px 32px;" align="center">
                <a href="{DASHBOARD_URL}" style="display:inline-block;background:#000;color:#facc15;font-weight:800;font-size:16px;text-decoration:none;padding:14px 32px;border:3px solid #000;border-radius:12px;box-shadow:4px 4px 0 #666;">
                  Go to Dashboard →
                </a>
              </td>
            </tr>
          </table>
          <p style="margin:20px 0 0 0;font-size:12px;color:#52525b;font-weight:600;text-align:center;">
            Questions? Reply to this email — it goes straight to the team.
          </p>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

    text = (
        f"Welcome, {name}.\n\n"
        "Your YeetCode Plus subscription is live. Every limit just turned into unlimited:\n\n"
        " · AI insights: unlimited\n"
        " · Frontend challenges: unlimited\n"
        " · Company-tagged problems: unlimited\n"
        " · Roadmap progress tracking: enabled\n"
        " · Streak freezes: 3 / month\n\n"
        f"Open the dashboard: {DASHBOARD_URL}\n\n"
        "Questions? Reply to this email — it goes straight to the team.\n"
    )

    try:
        result = resend.Emails.send(
            {
                "from": FROM_ADDRESS,
                "to": email,
                "subject": subject,
                "html": html,
                "text": text,
            }
        )
        info(f"[resend] welcome email sent to {email}: id={result.get('id')}")
        return True
    except Exception as e:
        error(f"[resend] welcome email failed for {email}: {e}")
        return False


def send_cancellation_email(
    email: Optional[str],
    display_name: Optional[str],
) -> bool:
    """Confirmation email when a Plus subscription is cancelled.

    Sent on customer.subscription.deleted. Does NOT raise.
    """
    if not email:
        warning("[resend] cancellation email skipped: no email")
        return False

    if not _configured():
        warning("[resend] cancellation email skipped: RESEND_API_KEY not set")
        return False

    name = display_name or "grinder"
    subject = "Your YeetCode Plus subscription has been cancelled."

    html = f"""\
<!DOCTYPE html>
<html>
  <body style="margin:0;padding:0;background:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#0a0a0a;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:40px 20px;">
      <tr>
        <td align="center">
          <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border:3px solid #000;border-radius:16px;box-shadow:6px 6px 0 #000;">
            <tr>
              <td style="padding:36px 32px 8px 32px;">
                <div style="display:inline-block;background:#52525b;color:#fff;font-weight:800;font-size:11px;letter-spacing:3px;text-transform:uppercase;padding:6px 14px;border-radius:999px;">
                  Subscription ended
                </div>
              </td>
            </tr>
            <tr>
              <td style="padding:8px 32px 0 32px;">
                <h1 style="margin:0;font-size:36px;line-height:1.05;font-weight:800;letter-spacing:-0.02em;">
                  Sorry to see you go,<br/>{name}.
                </h1>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 32px 0 32px;">
                <p style="margin:0;font-size:16px;line-height:1.5;color:#404040;font-weight:500;">
                  Your YeetCode Plus subscription has been cancelled and you've been moved back to the free tier. You'll keep access until the end of your current billing period.
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:24px 32px 0 32px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#fef9c3;border:2px solid #facc15;border-radius:12px;padding:16px;">
                  <tr>
                    <td>
                      <p style="margin:0;font-size:14px;font-weight:700;color:#0a0a0a;">Changed your mind?</p>
                      <p style="margin:6px 0 0 0;font-size:14px;color:#404040;line-height:1.5;">
                        You can resubscribe anytime from the dashboard — your history and progress are still here.
                      </p>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:28px 32px 32px 32px;" align="center">
                <a href="{DASHBOARD_URL}" style="display:inline-block;background:#000;color:#facc15;font-weight:800;font-size:16px;text-decoration:none;padding:14px 32px;border:3px solid #000;border-radius:12px;box-shadow:4px 4px 0 #666;">
                  Go to Dashboard →
                </a>
              </td>
            </tr>
          </table>
          <p style="margin:20px 0 0 0;font-size:12px;color:#52525b;font-weight:600;text-align:center;">
            Questions? Reply to this email — it goes straight to the team.
          </p>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

    text = (
        f"Hey {name},\n\n"
        "Your YeetCode Plus subscription has been cancelled. You've been moved back to the free tier "
        "and will keep access until the end of your current billing period.\n\n"
        "Changed your mind? You can resubscribe anytime from the dashboard — your history and "
        "progress are still here.\n\n"
        f"Dashboard: {DASHBOARD_URL}\n\n"
        "Questions? Reply to this email — it goes straight to the team.\n"
    )

    try:
        result = resend.Emails.send(
            {
                "from": FROM_ADDRESS,
                "to": email,
                "subject": subject,
                "html": html,
                "text": text,
            }
        )
        info(f"[resend] cancellation email sent to {email}: id={result.get('id')}")
        return True
    except Exception as e:
        error(f"[resend] cancellation email failed for {email}: {e}")
        return False
