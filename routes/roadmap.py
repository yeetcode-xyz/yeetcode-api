"""
Roadmap routes — Blind 75, NeetCode 150, NeetCode 250
"""

from collections import defaultdict
from fastapi import APIRouter, Depends

from auth import verify_api_key
from db import get_db

router = APIRouter(tags=["Roadmap"])

VALID_LISTS = {
    "blind75": "blind75_problems",
    "neetcode150": "neetcode150_problems",
    "neetcode250": "neetcode250_problems",
}


def _group_by_category(rows):
    """Group problem rows by category, preserving insertion order."""
    categories = defaultdict(list)
    for row in rows:
        d = dict(row)
        categories[d["category"]].append(d)
    return [{"name": cat, "problems": probs} for cat, probs in categories.items()]


@router.get("/roadmap/{list_name}")
async def get_roadmap_problems(
    list_name: str,
    api_key: str = Depends(verify_api_key)
):
    """Return all problems for a roadmap list, grouped by category."""
    table = VALID_LISTS.get(list_name)
    if not table:
        return {"success": False, "error": f"Invalid list. Use: {', '.join(VALID_LISTS)}"}

    conn = get_db()
    try:
        rows = conn.execute(
            f"SELECT * FROM {table} ORDER BY id"
        ).fetchall()
        categories = _group_by_category(rows)
        return {
            "success": True,
            "data": {
                "list_name": list_name,
                "total": len(rows),
                "categories": categories,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


@router.get("/roadmap/{list_name}/{username}")
async def get_roadmap_progress(
    list_name: str,
    username: str,
    api_key: str = Depends(verify_api_key)
):
    """Return problems + solved status for a user on a specific list."""
    table = VALID_LISTS.get(list_name)
    if not table:
        return {"success": False, "error": f"Invalid list. Use: {', '.join(VALID_LISTS)}"}

    norm_user = username.lower()
    conn = get_db()
    try:
        rows = conn.execute(
            f"""
            SELECT p.*, rp.solved_at
            FROM {table} p
            LEFT JOIN roadmap_progress rp
              ON rp.slug = p.slug
              AND rp.list_name = ?
              AND rp.username = ?
            ORDER BY p.id
            """,
            [list_name, norm_user],
        ).fetchall()

        total = len(rows)
        solved = 0
        categories = defaultdict(list)
        for row in rows:
            d = dict(row)
            is_solved = d.get("solved_at") is not None
            if is_solved:
                solved += 1
            d["solved"] = is_solved
            categories[d["category"]].append(d)

        cat_list = [{"name": cat, "problems": probs} for cat, probs in categories.items()]

        return {
            "success": True,
            "data": {
                "list_name": list_name,
                "total": total,
                "solved": solved,
                "categories": cat_list,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()
