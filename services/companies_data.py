"""
Company-tagged problems — reads from the separate companies.db SQLite file.
Schema: company_problems(company_id, problem_id, title, url, difficulty)
No separate companies table — company list is derived from distinct company_id values.
"""

import os
import sqlite3
from typing import Dict, List, Optional

COMPANIES_DB_PATH = os.environ.get("COMPANIES_DB_PATH", "/app/data/companies.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(COMPANIES_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _slug_from_id(company_id: str) -> str:
    """Normalize company_id to a URL-friendly slug."""
    return company_id.lower().replace(" ", "-").replace("_", "-")


def _display_name(company_id: str) -> str:
    """Convert company_id to a display name (e.g. 'accenture' -> 'Accenture')."""
    return company_id.replace("_", " ").replace("-", " ").title()


def list_companies() -> List[Dict]:
    """Return all companies with problem counts, sorted by count desc."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT company_id, COUNT(*) AS problem_count
            FROM company_problems
            GROUP BY company_id
            ORDER BY problem_count DESC, company_id ASC
            """
        ).fetchall()
        return [
            {
                "company_id": r["company_id"],
                "slug": _slug_from_id(r["company_id"]),
                "name": _display_name(r["company_id"]),
                "logo_url": None,
                "problem_count": r["problem_count"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def get_company(slug: str) -> Optional[Dict]:
    """Look up a company by slug. Since there's no companies table, we match against company_id."""
    conn = _get_conn()
    try:
        # Try exact match first, then case-insensitive
        row = conn.execute(
            """
            SELECT company_id, COUNT(*) AS problem_count
            FROM company_problems
            WHERE company_id = ? OR LOWER(company_id) = LOWER(?)
            GROUP BY company_id
            """,
            [slug, slug],
        ).fetchone()
        if not row:
            return None
        return {
            "company_id": row["company_id"],
            "slug": _slug_from_id(row["company_id"]),
            "name": _display_name(row["company_id"]),
            "logo_url": None,
            "problem_count": row["problem_count"],
        }
    finally:
        conn.close()


def get_problems(company_id: str) -> List[Dict]:
    """Return problems for a company, sorted by problem_id ascending."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT problem_id, title, difficulty, url
            FROM company_problems
            WHERE company_id = ? OR LOWER(company_id) = LOWER(?)
            ORDER BY problem_id ASC
            """,
            [company_id, company_id],
        ).fetchall()
        return [
            {
                "slug": _extract_slug(r["url"]),
                "title": r["title"],
                "difficulty": r["difficulty"].capitalize() if r["difficulty"] else "Medium",
                "leetcode_url": r["url"],
                "frequency": 0,
                "problem_id": r["problem_id"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def _extract_slug(url: str) -> str:
    """Extract problem slug from LeetCode URL like https://leetcode.com/problems/two-sum/"""
    if not url:
        return ""
    parts = url.rstrip("/").split("/")
    # URL format: .../problems/{slug}
    try:
        idx = parts.index("problems")
        return parts[idx + 1] if idx + 1 < len(parts) else ""
    except ValueError:
        return parts[-1] if parts else ""
