"""
Admin routes for YeetCode FastAPI server
Provides endpoints for managing background tasks and system operations
"""

import os
import logging
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

from auth import verify_api_key
from scheduler import get_scheduler_status, trigger_job_manually
from db import DB_PATH

router = APIRouter(tags=["Admin"], prefix="/admin")


def verify_api_key_query(api_key: str = Query(...)):
    """Verify API key from query parameter for browser-friendly endpoints"""
    expected_key = os.getenv("YETCODE_API_KEY")
    if not expected_key:
        raise HTTPException(status_code=500, detail="Server configuration error")
    if api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


# In-memory log storage (limited to last 500 entries)
log_buffer = []
MAX_LOGS = 500


class AdminLogHandler(logging.Handler):
    """Custom log handler that stores logs in memory for the admin dashboard"""

    def emit(self, record):
        try:
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S"),
                "level": record.levelname,
                "message": self.format(record),
                "logger": record.name
            }
            log_buffer.append(log_entry)
            if len(log_buffer) > MAX_LOGS:
                log_buffer.pop(0)
        except Exception:
            self.handleError(record)


background_logger = logging.getLogger("background_tasks")
admin_handler = AdminLogHandler()
admin_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
background_logger.addHandler(admin_handler)


@router.get("/scheduler/status")
async def get_scheduler_status_endpoint(
    api_key: str = Depends(verify_api_key)
):
    """Get the status of the background task scheduler"""
    try:
        status = get_scheduler_status()
        return {"success": True, "data": status}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/trigger/stats-update")
async def trigger_stats_update(
    api_key: str = Depends(verify_api_key)
):
    """Manually trigger the user stats update task"""
    try:
        result = await trigger_job_manually('update_user_stats')
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/trigger/bounty-update")
async def trigger_bounty_update(
    api_key: str = Depends(verify_api_key)
):
    """Manually trigger the bounty progress update task"""
    try:
        result = await trigger_job_manually('update_bounty_progress')
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/trigger/daily-problem")
async def trigger_daily_problem(
    api_key: str = Depends(verify_api_key)
):
    """Manually trigger the daily problem generation task"""
    try:
        result = await trigger_job_manually('generate_daily_problem')
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/logs", response_class=HTMLResponse)
async def serve_log_viewer(
    api_key: str = Depends(verify_api_key_query)
):
    """Serve the interactive log viewer"""
    try:
        html_path = os.path.join(os.path.dirname(__file__), "../static/log_viewer.html")

        if not os.path.exists(html_path):
            return HTMLResponse(
                content="<h1>Log viewer not found</h1><p>File: {}</p>".format(html_path),
                status_code=404
            )

        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except Exception as e:
        return HTMLResponse(
            content=f"<h1>Error loading log viewer</h1><p>{str(e)}</p>",
            status_code=500
        )


@router.get("/logs/content")
async def get_log_content(
    api_key: str = Depends(verify_api_key_query)
):
    """Get the raw log file content"""
    try:
        port = os.getenv("PORT", "6969")
        log_filename = "fastapi-dev.log" if port == "42069" else "fastapi.log"
        log_path = os.path.join(os.path.dirname(__file__), f"../{log_filename}")

        if not os.path.exists(log_path):
            raise HTTPException(status_code=404, detail=f"Log file not found at {log_path}")

        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()

        return {"success": True, "content": content, "path": log_path}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/db/status")
async def get_db_status(
    api_key: str = Depends(verify_api_key_query)
):
    """Get SQLite database stats

    Access via: /admin/db/status?api_key=YOUR_API_KEY
    """
    try:
        db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        table_counts = {}
        for table in ["users", "daily_problems", "daily_completions", "bounties", "bounty_progress", "duels", "verification_codes", "groups"]:
            row = conn.execute(f"SELECT COUNT(*) as n FROM {table}").fetchone()
            table_counts[table] = row["n"]
        conn.close()

        return {
            "success": True,
            "data": {
                "db_path":     DB_PATH,
                "db_size_mb":  round(db_size / 1024 / 1024, 2),
                "table_counts": table_counts,
                "timestamp":   datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/user/clear-invalid/{username}")
async def clear_leetcode_invalid(
    username: str,
    api_key: str = Depends(verify_api_key)
):
    """Clear the leetcode_invalid flag for a user so they appear in leaderboards"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE users SET leetcode_invalid = 0 WHERE username = ?", [username.lower()])
        conn.commit()
        affected = conn.total_changes
        conn.close()
        if affected == 0:
            return {"success": False, "error": f"User '{username}' not found"}
        return {"success": True, "message": f"Cleared leetcode_invalid for {username}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/trigger/backup")
async def trigger_backup(
    api_key: str = Depends(verify_api_key)
):
    """Manually trigger S3 backup"""
    try:
        result = await trigger_job_manually('backup_to_s3')
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


# Canonical bounty seed data — update this list when adding new bounties
BOUNTY_SEED = [
    # (bounty_id, title, description, slug, metric, count, start_date, expiry_date, xp, tags, difficulty_filter)
    ("bounty001", "Solve 3 Medium Problems",               "Solve any 3 medium LeetCode problems.",                         None, "medium", 3, 1774488273, 1779681600,  900, None,                  None),
    ("bounty002", "Solve 6 Easy BST Problems",             "Solve 6 LeetCode problems tagged with Binary Tree, Easy.",      None, "tag",    6, 1774488273, 1779681600,  750, "Binary Tree",         "Easy"),
    ("bounty003", "Solve 1 Hard Graph Problem",            "Solve a Hard LeetCode problem tagged with Graph.",              None, "tag",    1, 1774488273, 1779681600,  600, "Graph",               "Hard"),
    ("bounty004", "Solve 5 Easy Problems",                 "Solve any 5 Easy LeetCode problems.",                          None, "easy",   6, 1774488273, 1779681600,  600, None,                  None),
    ("bounty005", "Solve 7 Problems in a Week",            "Solve 7 LeetCode problems in any 7-day rolling window.",       None, "weekly", 7, 1774488273, 1779681600,  850, None,                  None),
    ("bounty006", "Solve 4 DP Problems",                   "Solve any 4 problems tagged with Dynamic Programming.",        None, "tag",    4, 1774488273, 1779681600,  850, "Dynamic Programming", None),
    ("bounty007", "Solve 3 Medium Binary Search Problems", "Solve 3 Medium problems tagged with Binary Search.",           None, "tag",    3, 1774488273, 1779681600, 1000, "Binary Search",       "Medium"),
    ("bounty008", "Solve 5 Graph Problems",                "Solve 5 LeetCode problems tagged with Graph.",                 None, "tag",    5, 1774488273, 1779681600, 1100, "Graph",               None),
    ("bounty009", "Solve 2 Hard Problems",                 "Solve any 2 Hard LeetCode problems.",                          None, "hard",   2, 1774488273, 1779681600, 1200, None,                  None),
    ("bounty010", "Solve 5 Daily Problems",                "Complete the daily challenge 5 times.",                        None, "daily",  5, 1774488273, 1779681600, 1000, None,                  None),
]


@router.post("/seed-bounties")
async def seed_bounties(
    api_key: str = Depends(verify_api_key)
):
    """Reset bounties table with canonical data and wipe all bounty progress.
    Safe to re-run — uses INSERT OR REPLACE so nothing is lost on bounties,
    but bounty_progress IS fully wiped.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        # Wipe all stale progress
        conn.execute("DELETE FROM bounty_progress")

        # Upsert all canonical bounties
        conn.executemany(
            """
            INSERT OR REPLACE INTO bounties
                (bounty_id, title, description, slug, metric, count, start_date, expiry_date, xp, tags, difficulty_filter)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            BOUNTY_SEED,
        )
        conn.commit()
        count = conn.execute("SELECT COUNT(*) as n FROM bounties").fetchone()["n"]
        conn.close()

        return {
            "success": True,
            "message": f"Seeded {len(BOUNTY_SEED)} bounties, wiped bounty_progress",
            "bounties_in_db": count,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
