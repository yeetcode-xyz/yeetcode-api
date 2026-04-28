"""
Company-tagged problems routes (mock data — see services/companies_data.py).

Free tier: 1 company-problem unlock per day (one slug, one company).
Plus tier: unlimited.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends

from auth import verify_api_key
from db import get_db
from services import companies_data, limits

router = APIRouter(tags=["Companies"])


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@router.get("/companies")
async def list_companies(api_key: str = Depends(verify_api_key)):
    """Return the list of companies with mock problem counts."""
    try:
        return {"success": True, "data": companies_data.list_companies()}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/companies/{slug}")
async def get_company(slug: str, api_key: str = Depends(verify_api_key)):
    """Return one company + its problems (with daily-unlock metadata for free tier)."""
    try:
        company = companies_data.get_company(slug)
        if not company:
            return {"success": False, "error": "Company not found"}

        problems = companies_data.get_problems(company["company_id"])
        return {
            "success": True,
            "data": {
                "company": company,
                "problems": problems,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/companies/unlock/status/{username}")
async def unlock_status(username: str, api_key: str = Depends(verify_api_key)):
    """Return whether the user has used today's free unlock + their tier."""
    try:
        tier = limits.get_tier(username)
        if tier == "plus":
            return {
                "success": True,
                "data": {
                    "tier": "plus",
                    "unlimited": True,
                    "unlocked_today": None,
                    "remaining_today": None,
                },
            }

        conn = get_db()
        try:
            row = conn.execute(
                "SELECT company_id, slug FROM company_problem_unlocks WHERE username = ? AND date = ?",
                [username.lower(), _today()],
            ).fetchone()
            return {
                "success": True,
                "data": {
                    "tier": "free",
                    "unlimited": False,
                    "unlocked_today": (
                        {"company_id": row["company_id"], "slug": row["slug"]} if row else None
                    ),
                    "remaining_today": 0 if row else 1,
                },
            }
        finally:
            conn.close()
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/companies/unlock")
async def unlock_problem(
    request: dict,
    api_key: str = Depends(verify_api_key),
):
    """Free tier: record one company-problem unlock for today.

    Body: {username, company_id, slug}
    Returns success=False if the user has already used today's unlock for a
    different problem. Re-unlocking the same problem is a no-op (idempotent).
    """
    username = (request.get("username") or "").lower()
    company_id = request.get("company_id") or ""
    slug = request.get("slug") or ""
    if not username or not company_id or not slug:
        return {"success": False, "error": "username, company_id, and slug required"}

    tier = limits.get_tier(username)
    if tier == "plus":
        return {"success": True, "data": {"tier": "plus", "unlimited": True}}

    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT company_id, slug FROM company_problem_unlocks WHERE username = ? AND date = ?",
            [username, _today()],
        ).fetchone()

        if existing:
            if existing["company_id"] == company_id and existing["slug"] == slug:
                return {
                    "success": True,
                    "data": {"tier": "free", "already_unlocked": True},
                }
            return {
                "success": False,
                "error": "Free tier: 1 company problem unlock per day. Upgrade to Plus for unlimited unlocks.",
                "code": "COMPANY_DAILY_CAP",
            }

        conn.execute(
            "INSERT INTO company_problem_unlocks (username, date, company_id, slug) VALUES (?, ?, ?, ?)",
            [username, _today(), company_id, slug],
        )
        conn.commit()
        return {
            "success": True,
            "data": {"tier": "free", "unlocked": {"company_id": company_id, "slug": slug}},
        }
    finally:
        conn.close()
