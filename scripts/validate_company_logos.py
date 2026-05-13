#!/usr/bin/env python3
"""Validate company logo mappings against local policy and optional CDN checks."""

import argparse
import os
import sqlite3
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

from services import companies_data  # noqa: E402


def _company_ids(min_problems: int, limit: int) -> set:
    conn = sqlite3.connect(f"file:{companies_data.DB_PATH}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            """
            SELECT company_id
            FROM company_problems
            GROUP BY company_id
            HAVING COUNT(*) >= ?
            ORDER BY COUNT(*) DESC
            LIMIT ?
            """,
            [min_problems, limit],
        ).fetchall()
        return {row[0] for row in rows}
    finally:
        conn.close()


def _cdn_ok(slug: str) -> bool:
    req = urllib.request.Request(
        f"https://cdn.simpleicons.org/{slug}?viewbox=auto",
        method="HEAD",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return 200 <= res.status < 400
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-problems", type=int, default=5)
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument(
        "--check-cdn",
        action="store_true",
        help="Also verify mapped Simple Icons slugs over the network.",
    )
    args = parser.parse_args()

    mapped = companies_data._SIMPLEICONS_LOGOS
    restricted = companies_data._SIMPLEICONS_RESTRICTED
    brandfetch_domains = companies_data._BRANDFETCH_DOMAINS
    ids = _company_ids(args.min_problems, args.limit)

    restricted_mapped = sorted(set(mapped) & restricted)
    brandfetch = ids & set(brandfetch_domains)
    unmapped = sorted(ids - set(mapped) - brandfetch)
    stale_mapped = sorted(set(mapped) - ids)
    stale_restricted = sorted(restricted - ids)

    print(f"Companies served by API defaults: {len(ids)}")
    print(f"Minimum problems: {args.min_problems}")
    print(f"Limit: {args.limit}")
    print(f"Mapped Simple Icons logos: {len(set(mapped) & ids)}")
    print(f"Mapped Brandfetch domains: {len(brandfetch)}")
    print(f"Restricted Brandfetch domains: {len(restricted & ids & set(brandfetch_domains))}")
    print(f"Unmapped fallbacks: {len(unmapped)}")

    if restricted_mapped:
        print("\nRestricted companies with logo mappings:")
        for company_id in restricted_mapped:
            print(f"  - {company_id}")

    if unmapped:
        print("\nCompanies using fallback tiles:")
        for company_id in unmapped:
            print(f"  - {company_id}")

    if stale_mapped:
        print("\nMapped logos not present in the current DB slice:")
        for company_id in stale_mapped:
            print(f"  - {company_id}")

    if stale_restricted:
        print("\nRestricted entries not present in the current DB slice:")
        for company_id in stale_restricted:
            print(f"  - {company_id}")

    if args.check_cdn:
        invalid = sorted(
            company_id for company_id, slug in mapped.items() if not _cdn_ok(slug)
        )
        if invalid:
            print("\nMapped slugs that did not resolve on cdn.simpleicons.org:")
            for company_id in invalid:
                print(f"  - {company_id}: {mapped[company_id]}")
            return 1

    return 1 if restricted_mapped else 0


if __name__ == "__main__":
    raise SystemExit(main())
