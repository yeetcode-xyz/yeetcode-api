"""
Daily SQLite → S3 backup for YeetCode

Uses sqlite3.backup() API which is safe with WAL mode (no lock needed).
Scheduled daily at 3 AM UTC via APScheduler.
"""

import os
import sqlite3
import logging
from datetime import date

log = logging.getLogger(__name__)

DB_PATH = os.environ.get("SQLITE_PATH", "/data/yeetcode.db")
S3_BACKUP_BUCKET = os.environ.get("S3_BACKUP_BUCKET")


def backup_to_s3():
    """Back up the SQLite database to S3."""
    if not S3_BACKUP_BUCKET:
        log.warning("⚠️ S3_BACKUP_BUCKET not set — skipping backup")
        return

    backup_path = f"/tmp/yeetcode_{date.today()}.db"

    try:
        # sqlite3.backup() is safe during WAL mode — no exclusive lock needed
        src = sqlite3.connect(DB_PATH)
        dst = sqlite3.connect(backup_path)
        src.backup(dst)
        src.close()
        dst.close()

        import boto3
        s3_key = f"backups/{date.today()}.db"
        boto3.client("s3").upload_file(backup_path, S3_BACKUP_BUCKET, s3_key)
        log.info(f"✅ Backup uploaded: s3://{S3_BACKUP_BUCKET}/{s3_key}")

    except Exception as e:
        log.error(f"❌ Backup failed: {e}")
    finally:
        if os.path.exists(backup_path):
            os.remove(backup_path)
