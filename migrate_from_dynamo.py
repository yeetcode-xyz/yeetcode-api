#!/usr/bin/env python3
"""
One-time migration script: DynamoDB → SQLite

Run this BEFORE switching the API to SQLite.
Scans all DynamoDB tables and inserts into SQLite.

Usage:
    SQLITE_PATH=/data/yeetcode.db python migrate_from_dynamo.py
"""

import os
import json
import time
import boto3
from dotenv import load_dotenv
from db import get_db, init_db

# Load env (for table names and AWS credentials)
env = os.environ.get("ENV", "prod")
env_file = f".env.{env}"
if os.path.exists(env_file):
    load_dotenv(env_file)
else:
    load_dotenv()

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
USERS_TABLE = os.environ.get("USERS_TABLE", "Yeetcode_users")
DAILY_TABLE = os.environ.get("DAILY_TABLE", "Daily")
DUELS_TABLE = os.environ.get("DUELS_TABLE", "Duels")
BOUNTIES_TABLE = os.environ.get("BOUNTIES_TABLE", "Bounties")

ddb = boto3.client("dynamodb", region_name=AWS_REGION)


_DDB_TYPES = {"S", "N", "BOOL", "M", "L", "SS", "NS", "BS", "NULL"}


def _is_ddb_typed(v):
    return isinstance(v, dict) and len(v) == 1 and next(iter(v)) in _DDB_TYPES


def _norm_value(v):
    """Normalize a single DynamoDB typed value to a plain Python value."""
    if not _is_ddb_typed(v):
        return v
    type_key = next(iter(v))
    if type_key == "S":
        return v["S"]
    elif type_key == "N":
        return int(float(v["N"]))
    elif type_key == "BOOL":
        return v["BOOL"]
    elif type_key == "M":
        return normalize(v["M"])
    elif type_key == "L":
        return [_norm_value(i) for i in v["L"]]
    elif type_key == "SS":
        return list(v["SS"])
    elif type_key == "NULL":
        return None
    return v


def normalize(item):
    """Recursively normalize a DynamoDB item (dict of typed values) to plain Python."""
    return {k: _norm_value(v) for k, v in item.items()}


def scan_all(table_name):
    """Paginated scan of a DynamoDB table, returns list of normalized items."""
    items = []
    params = {"TableName": table_name}
    while True:
        resp = ddb.scan(**params)
        for raw in resp.get("Items", []):
            items.append(normalize(raw))
        if "LastEvaluatedKey" not in resp:
            break
        params["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return items


def migrate_users(conn, users):
    """Migrate USERS_TABLE → users table."""
    count = 0
    skipped = 0
    for u in users:
        username = u.get("username", "")
        if not username or username.startswith("verification_"):
            skipped += 1
            continue

        conn.execute(
            """
            INSERT OR IGNORE INTO users
                (username, email, display_name, university, group_id,
                 easy, medium, hard, xp, streak,
                 last_completed_date, today, created_at, updated_at, leetcode_invalid)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                username.lower(),
                (u.get("email") or username).lower(),
                u.get("display_name") or username,
                u.get("university"),
                u.get("group_id") or None,
                int(u.get("easy") or 0),
                int(u.get("medium") or 0),
                int(u.get("hard") or 0),
                int(u.get("xp") or 0),
                int(u.get("streak") or 0),
                u.get("last_completed_date"),
                int(u.get("today") or 0),
                u.get("created_at"),
                u.get("updated_at"),
                1 if u.get("leetcode_invalid") else 0,
            ),
        )
        count += 1

    conn.commit()
    print(f"  Users: {count} migrated, {skipped} skipped (verification_ entries)")
    return count


def migrate_daily(conn, problems):
    """Migrate DAILY_TABLE → daily_problems + daily_completions."""
    prob_count = 0
    comp_count = 0

    for p in problems:
        date = p.get("date")
        slug = p.get("slug") or p.get("titleSlug")
        if not date or not slug:
            print(f"  Skipping daily problem with missing date or slug: {p}")
            continue

        tags = p.get("tags") or p.get("topicTags") or []
        if isinstance(tags, list):
            tags_json = json.dumps(tags)
        else:
            tags_json = json.dumps([])

        # difficulty: stored in DynamoDB only if generate_daily_problem saved it
        # Most old records won't have it — we store None (not 'Medium'!)
        difficulty = p.get("difficulty") or None

        conn.execute(
            """
            INSERT OR IGNORE INTO daily_problems
                (date, slug, title, frontend_id, difficulty, tags)
            VALUES (?,?,?,?,?,?)
            """,
            (date, slug, p.get("title"), p.get("frontendId"), difficulty, tags_json),
        )
        prob_count += 1

        # Expand users map → daily_completions rows
        users_map = p.get("users") or {}
        for username, completed in users_map.items():
            if completed:  # True or truthy value
                conn.execute(
                    "INSERT OR IGNORE INTO daily_completions (username, date) VALUES (?,?)",
                    (username.lower(), date),
                )
                comp_count += 1

    conn.commit()
    print(f"  Daily problems: {prob_count} migrated")
    print(f"  Daily completions: {comp_count} migrated")
    return prob_count, comp_count


def migrate_bounties(conn, bounties):
    """Migrate BOUNTIES_TABLE → bounties + bounty_progress."""
    bounty_count = 0
    progress_count = 0

    for b in bounties:
        # bounty_id may be stored as 'id' or 'bountyId'
        bounty_id = b.get("bountyId") or b.get("id")
        if not bounty_id:
            print(f"  Skipping bounty with no ID: {list(b.keys())}")
            continue

        conn.execute(
            """
            INSERT OR IGNORE INTO bounties
                (bounty_id, title, description, slug, metric, count,
                 start_date, expiry_date, xp)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                bounty_id,
                b.get("title"),
                b.get("description"),
                b.get("slug"),
                b.get("metric", "total").lower(),
                int(b.get("count") or 0),
                int(b.get("startdate") or b.get("start_date") or 0),
                int(b.get("expirydate") or b.get("expiry_date") or 0),
                int(b.get("xp") or 0),
            ),
        )
        bounty_count += 1

        # Expand users map → bounty_progress rows
        users_map = b.get("users") or {}
        for username, progress in users_map.items():
            conn.execute(
                """
                INSERT OR IGNORE INTO bounty_progress (bounty_id, username, progress)
                VALUES (?,?,?)
                """,
                (bounty_id, username.lower(), int(progress or 0)),
            )
            progress_count += 1

    conn.commit()
    print(f"  Bounties: {bounty_count} migrated")
    print(f"  Bounty progress: {progress_count} migrated")
    return bounty_count, progress_count


def migrate_duels(conn, duels):
    """Migrate DUELS_TABLE → duels (camelCase → snake_case)."""
    count = 0
    skipped = 0

    for d in duels:
        duel_id = d.get("duelId")
        challenger = d.get("challenger")
        challengee = d.get("challengee")
        if not duel_id or not challenger or not challengee:
            skipped += 1
            continue

        is_wager = 1 if (d.get("isWager") == "Yes" or d.get("isWager") is True) else 0

        conn.execute(
            """
            INSERT OR IGNORE INTO duels
                (duel_id, challenger, challengee, problem_slug, problem_title,
                 problem_number, difficulty, status, is_wager, challenger_wager,
                 challengee_wager, challenger_time, challengee_time,
                 challenger_start_time, challengee_start_time, start_time,
                 winner, xp_awarded, created_at, accepted_at, completed_at, expires_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                duel_id,
                challenger.lower(),
                challengee.lower(),
                d.get("problemSlug") or d.get("problem_slug"),
                d.get("problemTitle") or d.get("problem_title"),
                d.get("problemNumber") or d.get("problem_number"),
                d.get("difficulty"),
                d.get("status", "PENDING"),
                is_wager,
                int(d.get("challengerWager") or d.get("challenger_wager") or 0),
                int(d.get("challengeeWager") or d.get("challengee_wager") or 0),
                int(d.get("challengerTime") or d.get("challenger_time") or -1),
                int(d.get("challengeeTime") or d.get("challengee_time") or -1),
                d.get("challengerStartTime") or d.get("challenger_start_time"),
                d.get("challengeeStartTime") or d.get("challengee_start_time"),
                d.get("startTime") or d.get("start_time"),
                d.get("winner"),
                int(d.get("xpAwarded") or d.get("xp_awarded") or 0),
                d.get("createdAt") or d.get("created_at"),
                d.get("acceptedAt") or d.get("accepted_at"),
                d.get("completedAt") or d.get("completed_at"),
                int(d.get("expires_at") or 0),
            ),
        )
        count += 1

    conn.commit()
    print(f"  Duels: {count} migrated, {skipped} skipped")
    return count


def main():
    print(f"=== YeetCode DynamoDB → SQLite Migration ===")
    print(f"SQLite path: {os.environ.get('SQLITE_PATH', '/data/yeetcode.db')}")
    print(f"DynamoDB region: {AWS_REGION}")
    print()

    # Initialize schema
    print("Initializing SQLite schema...")
    init_db()
    conn = get_db()

    # Migrate users
    print(f"Scanning {USERS_TABLE}...")
    users = scan_all(USERS_TABLE)
    print(f"  Found {len(users)} items")
    migrate_users(conn, users)

    # Migrate daily problems
    print(f"\nScanning {DAILY_TABLE}...")
    problems = scan_all(DAILY_TABLE)
    print(f"  Found {len(problems)} items")
    migrate_daily(conn, problems)

    # Migrate bounties
    print(f"\nScanning {BOUNTIES_TABLE}...")
    bounties = scan_all(BOUNTIES_TABLE)
    print(f"  Found {len(bounties)} items")
    migrate_bounties(conn, bounties)

    # Migrate duels
    print(f"\nScanning {DUELS_TABLE}...")
    duels = scan_all(DUELS_TABLE)
    print(f"  Found {len(duels)} items")
    migrate_duels(conn, duels)

    # Summary
    print("\n=== Migration Summary ===")
    for table in ["users", "daily_problems", "daily_completions", "bounties", "bounty_progress", "duels"]:
        row = conn.execute(f"SELECT COUNT(*) as n FROM {table}").fetchone()
        print(f"  {table}: {row['n']} rows")

    conn.close()
    print("\n✅ Migration complete!")


if __name__ == "__main__":
    main()
