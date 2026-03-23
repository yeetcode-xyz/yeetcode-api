"""
Background tasks for YeetCode FastAPI server
"""

import asyncio
import logging
import random
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional
import os

from aws import (
    UserOperations, DailyProblemOperations, BountyOperations,
    _calc_total_xp,
)
from db import get_db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

DISCORD_LAMBDA_LOGS_WEBHOOK = os.environ.get("DISCORD_LAMBDA_LOGS_WEBHOOK")


def discord_log(message: str):
    if not DISCORD_LAMBDA_LOGS_WEBHOOK:
        return
    try:
        requests.post(DISCORD_LAMBDA_LOGS_WEBHOOK, json={"content": message}, timeout=5)
    except Exception as e:
        log.error(f"❌ Failed to send Discord log: {e}")


# ========================================
# TASK 1: Update User Stats
# ========================================

def fetch_user_stats(username: str) -> Optional[Dict]:
    """Fetch user stats from LeetCode GraphQL API.
    Returns None if the user definitively does not exist on LeetCode.
    Returns {} on transient errors (retry next cycle).
    """
    url   = "https://leetcode.com/graphql"
    query = """
      query getUserStats($username: String!) {
        matchedUser(username: $username) {
          submitStats: submitStatsGlobal {
            acSubmissionNum { difficulty count }
          }
        }
      }
    """
    payload = {"query": query, "variables": {"username": username}}

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        log.error(f"Error fetching stats for {username}: {e}")
        return {}

    matched_user = (data.get("data") or {}).get("matchedUser")
    if matched_user is None:
        return None

    easy = medium = hard = 0
    submissions = (matched_user.get("submitStats") or {}).get("acSubmissionNum") or []
    for item in submissions:
        difficulty = item.get("difficulty", "")
        count      = item.get("count", 0)
        if difficulty == "Easy":
            easy = count
        elif difficulty == "Medium":
            medium = count
        elif difficulty == "Hard":
            hard = count

    return {"easy": easy, "medium": medium, "hard": hard}


def check_daily_completion(username: str) -> Optional[str]:
    """Check if user completed today's daily problem. Returns slug if done, else None."""
    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")

        conn = get_db()
        try:
            row = conn.execute(
                "SELECT slug FROM daily_problems WHERE date = ?", [today]
            ).fetchone()
        finally:
            conn.close()

        if not row:
            return None
        slug = row["slug"]
        if not slug:
            return None

        query = """
          query recentSubmissions($username: String!, $limit: Int!) {
            recentSubmissionList(username: $username, limit: $limit) {
              status
              titleSlug
            }
          }
        """
        payload = {"query": query, "variables": {"username": username, "limit": 100}}
        response = requests.post("https://leetcode.com/graphql", json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()

        submissions = (data.get("data") or {}).get("recentSubmissionList") or []
        if any(sub.get("status") == 10 and sub.get("titleSlug") == slug for sub in submissions):
            return slug

        return None
    except Exception as e:
        log.error(f"Error checking daily completion for {username}: {e}")
        return None


async def process_single_user(username: str) -> bool:
    try:
        stats = await asyncio.to_thread(fetch_user_stats, username)

        if stats is None:
            log.warning(f"⚠️ {username} has no matching LeetCode account — flagging as invalid")
            UserOperations.update_user_data(username.lower(), {"leetcode_invalid": 1})
            return False

        if not stats:
            log.warning(f"⚠️ Failed to fetch stats for {username} (transient error)")
            return False

        user_data = UserOperations.get_user_data(username)
        if not user_data:
            log.warning(f"⚠️ User {username} not found in database")
            return False

        current_easy   = user_data.get("easy",   0) or 0
        current_medium = user_data.get("medium", 0) or 0
        current_hard   = user_data.get("hard",   0) or 0

        if (stats["easy"]   != current_easy or
            stats["medium"] != current_medium or
            stats["hard"]   != current_hard):

            # Update only easy/medium/hard — do NOT touch xp (it's bonus XP, managed separately)
            success = UserOperations.update_user_data(username.lower(), {
                "easy":   stats["easy"],
                "medium": stats["medium"],
                "hard":   stats["hard"],
            })
            if success:
                log.info(f"✅ Updated stats for {username}: {stats}")
            else:
                log.error(f"❌ Failed to update stats for {username}")

        # Check daily completion
        today      = datetime.utcnow().strftime("%Y-%m-%d")
        last_date  = user_data.get("last_completed_date")
        if last_date != today:
            completed_slug = await asyncio.to_thread(check_daily_completion, username)
            if completed_slug:
                DailyProblemOperations.complete_daily_problem(username.lower())
                log.info(f"🎯 {username} completed daily: {completed_slug}")

        return True
    except Exception as e:
        log.error(f"❌ Error processing user {username}: {e}")
        return False


async def update_user_stats():
    """Background task: Update all users' LeetCode stats. Runs every 1 minute."""
    log.info("🚀 Starting user stats update task...")

    try:
        result = UserOperations.get_all_users()
        if not result.get("success"):
            log.error("Failed to fetch users")
            return

        usernames = [
            u.get("username") for u in result.get("data", [])
            if u.get("username")
            and not u.get("username").startswith("verification_")
            and not u.get("leetcode_invalid")
        ]
        log.info(f"📊 Processing {len(usernames)} users...")

        semaphore = asyncio.Semaphore(30)

        async def process_with_limit(username):
            async with semaphore:
                return await process_single_user(username)

        results = await asyncio.gather(
            *[process_with_limit(u) for u in usernames],
            return_exceptions=True,
        )

        success_count = sum(1 for r in results if r is True)
        log.info(f"✅ Stats update complete: {success_count}/{len(usernames)} users processed")

    except Exception as e:
        log.error(f"❌ Error in update_user_stats: {e}")


# ========================================
# TASK 2: Update Bounty Progress
# ========================================

def get_user_metric_value(user_data: Dict, metric: str) -> int:
    if metric == "easy":
        return int(user_data.get("easy",   0) or 0)
    elif metric == "medium":
        return int(user_data.get("medium", 0) or 0)
    elif metric == "hard":
        return int(user_data.get("hard",   0) or 0)
    else:
        return (int(user_data.get("easy",   0) or 0) +
                int(user_data.get("medium", 0) or 0) +
                int(user_data.get("hard",   0) or 0))


async def update_bounty_progress():
    """Background task: Check all users' bounty progress. Runs every 5 minutes."""
    log.info("🎯 Starting bounty progress update task...")

    try:
        bounties_result = BountyOperations.get_all_bounties()
        if not bounties_result.get("success"):
            log.error("Failed to fetch bounties")
            return
        bounties = bounties_result.get("data", [])
        log.info(f"📦 Loaded {len(bounties)} bounties")

        users_result = UserOperations.get_all_users()
        if not users_result.get("success"):
            log.error("Failed to fetch users")
            return
        users = [
            u for u in users_result.get("data", [])
            if u.get("username")
            and not u.get("username").startswith("verification_")
            and not u.get("leetcode_invalid")
        ]
        log.info(f"👥 Processing {len(users)} users...")

        completion_count = 0

        for user in users:
            username = user.get("username")
            if not username:
                continue

            for bounty in bounties:
                # bounty_id is the column name; also aliased as bountyId/id for compat
                bounty_id = bounty.get("bounty_id") or bounty.get("bountyId") or bounty.get("id")
                if not bounty_id:
                    log.warning(f"⚠️ Skipping bounty with missing ID: {list(bounty.keys())}")
                    continue

                metric         = (bounty.get("metric") or "total").lower()
                required_count = int(bounty.get("count") or 0)
                xp_reward      = int(bounty.get("xp") or 0)

                user_value = get_user_metric_value(user, metric)

                # Check current progress from DB
                conn = get_db()
                try:
                    prev = conn.execute(
                        "SELECT progress FROM bounty_progress WHERE bounty_id = ? AND username = ?",
                        [bounty_id, username.lower()],
                    ).fetchone()
                    prev_progress = prev["progress"] if prev else 0
                finally:
                    conn.close()

                # Already completed
                if prev_progress >= required_count and required_count > 0:
                    continue

                if user_value >= required_count:
                    result = BountyOperations.update_bounty_progress(
                        username, bounty_id, user_value, xp_reward
                    )
                    if result.get("success"):
                        completion_count += 1
                        log.info(
                            f"✅ {username} completed bounty {bounty_id} "
                            f"({metric}: {user_value}/{required_count})"
                        )

        log.info(f"🏁 Bounty update complete: {completion_count} completions detected")

    except Exception as e:
        log.error(f"❌ Error in update_bounty_progress: {e}")


# ========================================
# TASK 3: Generate Daily Problem
# ========================================

def fetch_random_problem() -> Optional[Dict]:
    """Fetch a random Easy problem from LeetCode."""
    query = """
    query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
      problemsetQuestionList: questionList(
        categorySlug: $categorySlug,
        limit: $limit,
        skip: $skip,
        filters: $filters
      ) {
        total: totalNum
        questions: data {
          title
          titleSlug
          difficulty
          frontendQuestionId: questionFrontendId
          paidOnly: isPaidOnly
          topicTags {
            name
          }
        }
      }
    }
    """

    for attempt in range(5):
        skip = random.randint(0, 700)
        log.info(f"🎲 Attempt {attempt + 1}: skip index {skip}")

        variables = {
            "categorySlug": "",
            "limit": 1,
            "skip": skip,
            "filters": {"difficulty": "EASY"},
        }

        try:
            response = requests.post(
                "https://leetcode.com/graphql",
                json={"query": query, "variables": variables},
                timeout=10,
            )
            if response.status_code != 200:
                log.error(f"❌ LeetCode API failed: {response.status_code}")
                continue

            data      = response.json()
            questions = data.get("data", {}).get("problemsetQuestionList", {}).get("questions", [])
            if not questions:
                log.warning("⚠️ No questions found")
                continue

            problem = questions[0]
            if not problem.get("paidOnly"):
                return problem
            log.info(f"💸 Skipped paid-only: {problem['title']}")

        except Exception as e:
            log.error(f"Error fetching problem: {e}")
            continue

    return None


async def generate_daily_problem():
    """Background task: Generate a new daily problem. Runs once daily at 00:00 UTC."""
    date = datetime.utcnow().strftime("%Y-%m-%d")
    log.info(f"🚀 Generating daily problem for {date}")
    discord_log(f"🚀 Generating daily problem for {date}")

    try:
        problem = await asyncio.to_thread(fetch_random_problem)
        if not problem:
            log.error("❌ No valid free problem found after retries")
            discord_log("❌ No valid free problem found after retries")
            return

        tags = [tag["name"] for tag in problem.get("topicTags", [])]
        if not tags:
            tags = ["No Problem Tags"]

        # Save to SQLite with correct difficulty (from LeetCode response)
        success = DailyProblemOperations.save_daily_problem(
            date        = date,
            slug        = problem["titleSlug"],
            title       = problem["title"],
            frontend_id = problem["frontendQuestionId"],
            difficulty  = problem.get("difficulty", "Easy"),  # LeetCode returns "Easy" for easy problems
            tags        = tags,
        )

        if success:
            log.info(f"✅ Daily problem saved: {problem['title']} ({problem.get('difficulty')})")
            discord_log(f"✅ Daily problem set: {problem['titleSlug']}")
        else:
            log.error("❌ Failed to save daily problem to SQLite")
            discord_log("❌ Failed to save daily problem")

    except Exception as e:
        log.error(f"❌ Error generating daily problem: {e}")
        discord_log(f"❌ Error generating daily problem: {e}")
