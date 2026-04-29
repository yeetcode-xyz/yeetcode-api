"""
Company-tagged problems from the separate companies.db SQLite file.

The company list is derived from distinct company_id values in company_problems.
Logo URLs use Simple Icons when an allowed slug exists, then optional Brandfetch
domain lookups for protected or unmapped brands when BRANDFETCH_CLIENT_ID is set.
"""

import os
import sqlite3
from typing import Dict, List, Optional
from urllib.parse import quote

_ROOT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "companies.db")
_DEPLOY_DB_PATH = "/app/data/companies.db"
COMPANIES_DB_PATH = os.environ.get("COMPANIES_DB_PATH") or (
    _DEPLOY_DB_PATH if os.path.exists(_DEPLOY_DB_PATH) else _ROOT_DB_PATH
)
DB_PATH = COMPANIES_DB_PATH

_DISPLAY_NAMES: Dict[str, str] = {
    "tcs": "TCS",
    "ibm": "IBM",
    "goldman-sachs": "Goldman Sachs",
    "walmart-labs": "Walmart Labs",
    "jp-morgan": "JP Morgan",
    "jpmorgan": "JP Morgan",
    "6sense": "6sense",
    "1kosmos": "1Kosmos",
    "servicenow": "ServiceNow",
    "paypal": "PayPal",
    "salesforce": "Salesforce",
    "tiktok": "TikTok",
    "linkedin": "LinkedIn",
    "nvidia": "NVIDIA",
    "airbnb": "Airbnb",
}

# Simple Icons does not carry every company logo, and some high-value interview
# companies are explicitly disallowed by its brand policy. Keep this as an
# allowlist instead of deriving slugs from company names.
_SIMPLEICONS_LOGOS: Dict[str, str] = {
    "accenture": "accenture",
    "adobe": "adobe",
    "airbnb": "airbnb",
    "apple": "apple",
    "atlassian": "atlassian",
    "bloomberg": "bloomberg",
    "booking.com": "bookingdotcom",
    "bookingcom": "bookingdotcom",
    "capgemini": "capgemini",
    "cisco": "cisco",
    "cloudflare": "cloudflare",
    "coinbase": "coinbase",
    "cognizant": "cognizant",
    "crowdstrike": "crowdstrike",
    "databricks": "databricks",
    "datadog": "datadog",
    "dell": "dell",
    "deloitte": "deloitte",
    "doordash": "doordash",
    "dropbox": "dropbox",
    "ebay": "ebay",
    "epic-games": "epicgames",
    "expedia": "expedia",
    "goldman-sachs": "goldmansachs",
    "google": "google",
    "hcl": "hcl",
    "hubspot": "hubspot",
    "ibm": "ibm",
    "indeed": "indeed",
    "infosys": "infosys",
    "intel": "intel",
    "intuit": "intuit",
    "jp-morgan": "jpmorgan",
    "jpmorgan": "jpmorgan",
    "lyft": "lyft",
    "meta": "meta",
    "mongodb": "mongodb",
    "netflix": "netflix",
    "nvidia": "nvidia",
    "palo-alto-networks": "paloaltonetworks",
    "paypal": "paypal",
    "pinterest": "pinterest",
    "qualcomm": "qualcomm",
    "reddit": "reddit",
    "roblox": "roblox",
    "salesforce": "salesforce",
    "samsung": "samsung",
    "sap": "sap",
    "servicenow": "servicenow",
    "shopify": "shopify",
    "siemens": "siemens",
    "snap": "snapchat",
    "snapchat": "snapchat",
    "snowflake": "snowflake",
    "spotify": "spotify",
    "stripe": "stripe",
    "tcs": "tcs",
    "tiktok": "tiktok",
    "twitter": "x",
    "uber": "uber",
    "unity": "unity",
    "visa": "visa",
    "vmware": "vmware",
    "walmart-labs": "walmart",
    "wipro": "wipro",
    "workday": "workday",
    "wix": "wix",
    "zendesk": "zendesk",
    "zoho": "zoho",
}

# Documented so future edits do not accidentally add these back to the allowlist.
_SIMPLEICONS_RESTRICTED: set = {
    "amazon",
    "aws",
    "bp",
    "disney",
    "international-olympic-committee",
    "java",
    "linkedin",
    "marvel",
    "mattel",
    "microchip",
    "microchip-technology",
    "microsoft",
    "oracle",
    "playwright",
    "twilio",
    "visual-studio",
    "yahoo",
}

_BRANDFETCH_DOMAINS: Dict[str, str] = {
    "agoda": "agoda.com",
    "amazon": "amazon.com",
    "anduril": "anduril.com",
    "arista-networks": "arista.com",
    "aws": "aws.amazon.com",
    "bytedance": "bytedance.com",
    "capital-one": "capitalone.com",
    "citadel": "citadel.com",
    "coupang": "coupang.com",
    "de-shaw": "deshaw.com",
    "disney": "disney.com",
    "epam-systems": "epam.com",
    "flipkart": "flipkart.com",
    "linkedin": "linkedin.com",
    "meesho": "meesho.com",
    "microsoft": "microsoft.com",
    "morgan-stanley": "morganstanley.com",
    "nutanix": "nutanix.com",
    "oracle": "oracle.com",
    "phonepe": "phonepe.com",
    "sprinklr": "sprinklr.com",
    "swiggy": "swiggy.com",
    "tesla": "tesla.com",
    "twilio": "twilio.com",
    "yahoo": "yahoo.com",
    "yandex": "yandex.com",
}


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(COMPANIES_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _slug_from_id(company_id: str) -> str:
    """Normalize company_id to a URL-friendly slug."""
    return company_id.lower().replace(" ", "-").replace("_", "-")


def _display_name(company_id: str) -> str:
    if company_id in _DISPLAY_NAMES:
        return _DISPLAY_NAMES[company_id]
    return company_id.replace("_", " ").replace("-", " ").title()


def _brandfetch_client_id() -> Optional[str]:
    client_id = os.getenv("BRANDFETCH_CLIENT_ID", "").strip()
    return client_id or None


def _brandfetch_logo_url(company_id: str) -> Optional[str]:
    client_id = _brandfetch_client_id()
    domain = _BRANDFETCH_DOMAINS.get(company_id)
    if not client_id or not domain:
        return None
    return (
        f"https://cdn.brandfetch.io/domain/{quote(domain)}/w/128/h/128/"
        f"fallback/404/type/icon?c={quote(client_id)}"
    )


def _logo_url(company_id: str) -> Optional[str]:
    if company_id not in _SIMPLEICONS_RESTRICTED:
        slug = _SIMPLEICONS_LOGOS.get(company_id)
        if slug:
            return f"https://cdn.simpleicons.org/{slug}?viewbox=auto"
    return _brandfetch_logo_url(company_id)


def list_companies(
    min_problems: int = 5,
    limit: int = 60,
    search: Optional[str] = None,
) -> List[Dict]:
    """Return companies with problem counts, sorted by count desc."""
    conn = _get_conn()
    try:
        params = []
        where = ""
        normalized_search = (search or "").strip().lower()
        if normalized_search:
            like = f"%{normalized_search}%"
            spaced_like = f"%{normalized_search.replace('-', ' ')}%"
            dashed_like = f"%{normalized_search.replace(' ', '-')}%"
            where = """
            WHERE LOWER(company_id) LIKE ?
               OR LOWER(REPLACE(company_id, '-', ' ')) LIKE ?
               OR LOWER(REPLACE(company_id, ' ', '-')) LIKE ?
            """
            params.extend([like, spaced_like, dashed_like])
        params.extend([min_problems, limit])

        rows = conn.execute(
            f"""
            SELECT company_id, COUNT(*) AS problem_count
            FROM company_problems
            {where}
            GROUP BY company_id
            HAVING problem_count >= ?
            ORDER BY problem_count DESC, company_id ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [
            {
                "company_id": r["company_id"],
                "slug": _slug_from_id(r["company_id"]),
                "name": _display_name(r["company_id"]),
                "logo_url": _logo_url(r["company_id"]),
                "problem_count": r["problem_count"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def get_company(slug: str) -> Optional[Dict]:
    """Look up a company by URL slug or company_id."""
    conn = _get_conn()
    try:
        row = conn.execute(
            """
            SELECT company_id, COUNT(*) AS problem_count
            FROM company_problems
            WHERE company_id = ?
               OR LOWER(company_id) = LOWER(?)
               OR LOWER(REPLACE(REPLACE(company_id, ' ', '-'), '_', '-')) = LOWER(?)
            GROUP BY company_id
            """,
            [slug, slug, slug],
        ).fetchone()
        if not row:
            return None
        cid = row["company_id"]
        return {
            "company_id": cid,
            "slug": _slug_from_id(cid),
            "name": _display_name(cid),
            "logo_url": _logo_url(cid),
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
            WHERE company_id = ?
               OR LOWER(company_id) = LOWER(?)
               OR LOWER(REPLACE(REPLACE(company_id, ' ', '-'), '_', '-')) = LOWER(?)
            ORDER BY problem_id ASC
            """,
            [company_id, company_id, company_id],
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
    """Extract problem slug from a LeetCode problem URL."""
    if not url:
        return ""
    parts = url.rstrip("/").split("/")
    try:
        idx = parts.index("problems")
        return parts[idx + 1] if idx + 1 < len(parts) else ""
    except ValueError:
        return parts[-1] if parts else ""
