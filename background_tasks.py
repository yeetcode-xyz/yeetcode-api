"""
Background tasks for YeetCode FastAPI server
"""

import asyncio
import logging
import random
import json
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import os

from aws import (
    UserOperations, DailyProblemOperations, BountyOperations, DuelOperations,
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


def fetch_user_tag_stats(username: str) -> Optional[Dict[str, int]]:
    """Fetch per-tag solved counts from LeetCode.
    Returns {tagName: problemsSolved} or None if user not found, {} on transient error.
    """
    query = """
      query skillStats($username: String!) {
        matchedUser(username: $username) {
          tagProblemCounts {
            advanced     { tagName problemsSolved }
            intermediate { tagName problemsSolved }
            fundamental  { tagName problemsSolved }
          }
        }
      }
    """
    try:
        response = requests.post(
            "https://leetcode.com/graphql",
            json={"query": query, "variables": {"username": username}},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        log.error(f"Error fetching tag stats for {username}: {e}")
        return {}

    matched_user = (data.get("data") or {}).get("matchedUser")
    if matched_user is None:
        return None

    counts: Dict[str, int] = {}
    tag_data = (matched_user.get("tagProblemCounts") or {})
    for category in ("advanced", "intermediate", "fundamental"):
        for item in (tag_data.get(category) or []):
            tag_name = item.get("tagName")
            solved   = item.get("problemsSolved", 0)
            if tag_name:
                counts[tag_name] = solved
    return counts


def fetch_user_weekly_count(username: str) -> int:
    """Count unique problems solved by the user in the last 7 days.
    Returns 0 on any error.
    """
    query = """
      query recentAcSubmissions($username: String!, $limit: Int!) {
        recentAcSubmissionList(username: $username, limit: $limit) {
          titleSlug
          timestamp
        }
      }
    """
    try:
        response = requests.post(
            "https://leetcode.com/graphql",
            json={"query": query, "variables": {"username": username, "limit": 100}},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        log.error(f"Error fetching weekly count for {username}: {e}")
        return 0

    submissions = (data.get("data") or {}).get("recentAcSubmissionList") or []
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=7)
    seen: set = set()
    for sub in submissions:
        ts = sub.get("timestamp")
        slug = sub.get("titleSlug")
        if not ts or not slug:
            continue
        try:
            sub_dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        except Exception:
            continue
        if sub_dt >= cutoff:
            seen.add(slug)
    return len(seen)


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

            # Rank overtake notifications
            try:
                bonus_xp  = int(user_data.get("xp") or 0)
                old_total = current_easy * 100 + current_medium * 300 + current_hard * 500 + bonus_xp
                new_total = stats["easy"] * 100 + stats["medium"] * 300 + stats["hard"] * 500 + bonus_xp
                group_id  = user_data.get("group_id")
                if new_total > old_total and group_id:
                    conn = get_db()
                    try:
                        overtaken = conn.execute(
                            """
                            SELECT username FROM users
                            WHERE group_id = ? AND username != ?
                              AND (easy * 100 + medium * 300 + hard * 500 + xp) > ?
                              AND (easy * 100 + medium * 300 + hard * 500 + xp) <= ?
                            """,
                            [group_id, username.lower(), old_total, new_total],
                        ).fetchall()
                    finally:
                        conn.close()
                    if overtaken:
                        from push_service import send_push
                        display = user_data.get("display_name") or username
                        for row in overtaken:
                            send_push(
                                row["username"],
                                "📉 You've been overtaken!",
                                f"{display} just passed you on the leaderboard!",
                            )
            except Exception as e:
                log.warning(f"Rank overtake push failed for {username}: {e}")

        # Cache tag stats + weekly count (used by bounty task — reads from DB, no extra LeetCode calls)
        tag_stats_result = await asyncio.to_thread(fetch_user_tag_stats, username)
        if tag_stats_result is not None and tag_stats_result != {}:
            UserOperations.update_user_data(username.lower(), {
                "tag_stats": json.dumps(tag_stats_result),
            })

        weekly_count = await asyncio.to_thread(fetch_user_weekly_count, username)
        UserOperations.update_user_data(username.lower(), {"weekly_solved": weekly_count})

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

def get_user_metric_value(user_data: Dict, bounty: Dict, conn, username: str) -> int:
    """Compute a user's progress value for a bounty. Reads only from user_data (DB-cached)."""
    metric = (bounty.get("metric") or "total").lower()
    tag    = bounty.get("tags")

    if metric == "easy":
        return int(user_data.get("easy",   0) or 0)
    if metric == "medium":
        return int(user_data.get("medium", 0) or 0)
    if metric == "hard":
        return int(user_data.get("hard",   0) or 0)
    if metric == "weekly":
        return int(user_data.get("weekly_solved", 0) or 0)
    if metric == "daily":
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM daily_completions WHERE username = ?",
                [username.lower()],
            ).fetchone()
            return row["c"] if row else 0
        except Exception:
            return 0
    if metric == "tag":
        raw = user_data.get("tag_stats") or "{}"
        try:
            stats = json.loads(raw)
        except Exception:
            return 0
        return stats.get(tag, 0) if tag else 0
    # default: total
    return (int(user_data.get("easy",   0) or 0) +
            int(user_data.get("medium", 0) or 0) +
            int(user_data.get("hard",   0) or 0))


async def update_bounty_progress():
    """Background task: Check all users' bounty progress. Runs every 5 minutes.
    Reads only from DB — no LeetCode API calls (tag/weekly stats cached by update_user_stats).
    """
    log.info("🎯 Starting bounty progress update task...")

    try:
        # Load active bounties only
        now = int(datetime.utcnow().timestamp())
        conn = get_db()
        try:
            bounty_rows = conn.execute(
                "SELECT * FROM bounties WHERE start_date <= ? AND expiry_date >= ?",
                [now, now],
            ).fetchall()
        finally:
            conn.close()

        bounties = [dict(r) for r in bounty_rows]
        if not bounties:
            log.info("📦 No active bounties to process")
            return
        log.info(f"📦 Loaded {len(bounties)} active bounties")

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
        progress_count   = 0

        for user in users:
            username = user.get("username")
            if not username:
                continue

            conn = get_db()
            try:
                for bounty in bounties:
                    bounty_id = bounty.get("bounty_id")
                    if not bounty_id:
                        continue

                    required_count = int(bounty.get("count") or 0)
                    xp_reward      = int(bounty.get("xp") or 0)

                    new_progress = get_user_metric_value(user, bounty, conn, username)

                    # Fetch previous progress + completion state
                    prev_row = conn.execute(
                        "SELECT progress, xp_awarded FROM bounty_progress WHERE bounty_id = ? AND username = ?",
                        [bounty_id, username.lower()],
                    ).fetchone()
                    prev_progress = prev_row["progress"]   if prev_row else 0
                    xp_already    = prev_row["xp_awarded"] if prev_row else 0

                    # Never decrease progress (guards against transient API gaps)
                    if new_progress < prev_progress:
                        continue

                    # No change — skip
                    if new_progress == prev_progress:
                        continue

                    # 80% milestone notification (fire only when crossing the threshold)
                    if required_count > 0:
                        old_pct = (prev_progress / required_count) * 100
                        new_pct = (new_progress  / required_count) * 100
                        if old_pct < 80 <= new_pct and new_pct < 100:
                            remaining = required_count - new_progress
                            try:
                                from push_service import send_push
                                bounty_title = bounty.get("title") or "a bounty"
                                send_push(
                                    username,
                                    "🔥 Almost there!",
                                    f"Only {remaining} more to complete '{bounty_title}'",
                                )
                            except Exception:
                                pass

                    result = BountyOperations.update_bounty_progress(
                        username, bounty_id, new_progress, xp_reward,
                        already_awarded=bool(xp_already),
                    )
                    if result.get("success"):
                        progress_count += 1
                        if result.get("completed"):
                            completion_count += 1
                            log.info(
                                f"✅ {username} completed bounty {bounty_id} "
                                f"(progress: {new_progress}/{required_count})"
                            )
                            try:
                                from push_service import send_push
                                bounty_title = bounty.get("title") or "a bounty"
                                send_push(
                                    username,
                                    "🎯 Bounty Complete!",
                                    f"You earned {xp_reward} XP for completing '{bounty_title}'",
                                )
                            except Exception:
                                pass
            finally:
                conn.close()

        log.info(
            f"🏁 Bounty update complete: {completion_count} completions, "
            f"{progress_count} progress updates"
        )

    except Exception as e:
        log.error(f"❌ Error in update_bounty_progress: {e}")


# ========================================
# TASK 3: Generate Daily Problem
# ========================================

def fetch_random_problem(difficulty: str = "EASY") -> Optional[Dict]:
    """Fetch a random problem from LeetCode for the given difficulty."""
    difficulty = (difficulty or "EASY").upper()
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
            "filters": {"difficulty": difficulty},
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


# ========================================
# TASK 4: Poll Active Duels
# ========================================

def check_duel_solve(username: str, problem_slug: str, start_time_iso: str) -> Optional[int]:
    """
    Check LeetCode for an accepted submission of problem_slug by username
    submitted after start_time_iso.

    Returns elapsed_ms (from start_time to submission timestamp) if found,
    or None if not found.
    """
    query = """
      query recentAcSubmissions($username: String!, $limit: Int!) {
        recentAcSubmissionList(username: $username, limit: $limit) {
          titleSlug
          timestamp
        }
      }
    """
    try:
        start_dt = datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
    except Exception:
        start_dt = None

    try:
        response = requests.post(
            "https://leetcode.com/graphql",
            json={"query": query, "variables": {"username": username, "limit": 20}},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        log.error(f"LeetCode check_duel_solve error for {username}: {e}")
        return None

    submissions = (data.get("data") or {}).get("recentAcSubmissionList") or []
    for sub in submissions:
        if sub.get("titleSlug") != problem_slug:
            continue
        ts = sub.get("timestamp")
        if not ts:
            continue
        try:
            sub_dt = datetime.fromtimestamp(int(ts), tz=__import__("datetime").timezone.utc)
        except Exception:
            continue
        # Must be submitted after the duel start
        if start_dt and sub_dt < start_dt:
            continue
        if start_dt:
            elapsed_ms = int((sub_dt - start_dt).total_seconds() * 1000)
        else:
            elapsed_ms = 0
        return elapsed_ms

    return None


async def poll_active_duels():
    """
    Background task: Check active duels every 3 seconds.
    For each user in an active duel who hasn't submitted yet,
    poll LeetCode's recent accepted submissions.
    """
    try:
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM duels WHERE status = 'ACTIVE'"
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return

        for row in rows:
            duel = dict(row)
            duel_id      = duel.get("duel_id")
            problem_slug = duel.get("problem_slug")
            challenger   = duel.get("challenger")
            challengee   = duel.get("challengee")
            c_time       = duel.get("challenger_time", -1)
            e_time       = duel.get("challengee_time", -1)
            c_start      = duel.get("challenger_start_time")
            e_start      = duel.get("challengee_start_time")

            if not problem_slug:
                continue

            tasks = []
            # Check challenger if they've started (time == 0) but not yet submitted (time > 0)
            if c_time == 0 and c_start:
                tasks.append(("challenger", challenger, c_start))
            # Check challengee
            if e_time == 0 and e_start:
                tasks.append(("challengee", challengee, e_start))

            for role, username, start_iso in tasks:
                elapsed_ms = await asyncio.to_thread(
                    check_duel_solve, username, problem_slug, start_iso
                )
                if elapsed_ms is not None:
                    log.info(
                        f"🎯 Duel poll: {username} solved {problem_slug} "
                        f"in {elapsed_ms}ms (duel {duel_id})"
                    )
                    DuelOperations.record_duel_submission(username, duel_id, elapsed_ms)

    except Exception as e:
        log.error(f"❌ Error in poll_active_duels: {e}")
