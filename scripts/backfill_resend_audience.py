"""
One-time backfill: add all existing non-guest users with emails into the Resend audience.

Usage:
    RESEND_API_KEY=re_... RESEND_AUDIENCE_ID=<uuid> python scripts/backfill_resend_audience.py

Idempotent — Resend Contacts.create upserts by email, so safe to re-run.
"""

import os
import sys
import time
import sqlite3

import resend

DB_PATH = os.getenv("DB_PATH", "companies.db")
AUDIENCE_ID = os.getenv("RESEND_AUDIENCE_ID", "")
API_KEY = os.getenv("RESEND_API_KEY", "")

if not API_KEY or not AUDIENCE_ID:
    print("ERROR: set RESEND_API_KEY and RESEND_AUDIENCE_ID")
    sys.exit(1)

resend.api_key = API_KEY

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT email, display_name, university, tier FROM users "
    "WHERE email IS NOT NULL AND (is_guest IS NULL OR is_guest = 0)"
).fetchall()
conn.close()

print(f"Backfilling {len(rows)} users...")

ok = fail = 0
for row in rows:
    email = row["email"]
    display_name = row["display_name"] or ""
    university = row["university"]
    tier = row["tier"] or "free"

    parts = display_name.strip().split(" ", 1)
    first_name = parts[0] if parts[0] else None
    last_name = parts[1] if len(parts) > 1 else None

    params: dict = {
        "audience_id": AUDIENCE_ID,
        "email": email,
        "unsubscribed": False,
        "data": {"tier": tier, **({"university": university} if university else {})},
    }
    if first_name:
        params["first_name"] = first_name
    if last_name:
        params["last_name"] = last_name

    try:
        resend.Contacts.create(params)
        ok += 1
    except Exception as e:
        print(f"  FAIL {email}: {e}")
        fail += 1

    # Resend free tier rate limit: 5 req/s
    time.sleep(0.2)

print(f"Done: {ok} added, {fail} failed")
