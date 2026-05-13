# YeetCode API

FastAPI backend for [YeetCode](https://yeetcode.xyz) — a competitive LeetCode platform with duels, XP, streaks, and group leaderboards.

## Tech Stack

- **FastAPI** — Python web framework
- **SQLite** — Primary database (WAL mode, immediate durability)
- **Resend** — Transactional email (OTP + duel invites)
- **APScheduler** — Background job scheduler
- **LeetCode GraphQL** — Pulls problem data and verifies submissions
- **S3** — Daily database backups (optional)
- **Discord webhooks** — Logging (optional)

---

## Local Setup

### Prerequisites

- Python 3.10+
- No database setup needed — SQLite creates itself on first run

### Install

```bash
git clone https://github.com/yeetcode-xyz/yeetcode-api.git
cd yeetcode-api

python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Fill in .env (see Environment Variables below)
```

### Run

```bash
uvicorn main:app --reload --port 6969
```

API is at `http://localhost:6969`. Interactive docs at `/docs`.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `YETCODE_API_KEY` | Yes | Key used by the frontend to authenticate requests |
| `RESEND_API_KEY` | Yes | Resend API key for sending emails |
| `SQLITE_PATH` | No | Path to SQLite file (default: `/data/yeetcode.db`) |
| `DEBUG_MODE` | No | Set `true` to enable verbose logs |
| `DISCORD_WEBHOOK_URL` | No | Discord webhook for new user notifications |
| `DISCORD_LAMBDA_LOGS_WEBHOOK` | No | Discord webhook for background task logs |
| `BACKUP_S3_BUCKET` | No | S3 bucket name for daily DB backups |
| `AWS_ACCESS_KEY_ID` | No | Only needed if using S3 backups |
| `AWS_SECRET_ACCESS_KEY` | No | Only needed if using S3 backups |
| `AWS_REGION` | No | AWS region (default: `us-east-1`) |
| `BRANDFETCH_CLIENT_ID` | No | Enables Brandfetch logo URLs for companies that are unavailable in Simple Icons |

> The old DynamoDB table name variables (`USERS_TABLE`, `DAILY_TABLE`, etc.) are only needed if running `migrate_from_dynamo.py`.

---

## Project Structure

```
yeetcode-api/
│
├── main.py                  # FastAPI app, startup (init_db), route registration
├── db.py                    # SQLite connection, schema definition, init_db()
├── aws.py                   # All database operations (UserOperations, DuelOperations, etc.)
├── auth.py                  # API key verification middleware
├── models.py                # Pydantic request/response models
│
├── routes/
│   ├── auth.py              # /login, /verify, /store-verification-code
│   ├── users.py             # /user, /leaderboard, /update-stats
│   ├── groups.py            # /create-group, /join-group, /group-stats, /university-leaderboard
│   ├── daily.py             # /daily-problem, /complete-daily-problem
│   ├── duels.py             # /duels, /create-duel, /accept-duel, /start-duel, /verify-duel-solve, + more
│   ├── bounties.py          # /bounties, /bounty-progress
│   └── admin.py             # /admin/stats, /admin/db-info
│
├── background_tasks.py      # LeetCode polling: stats sync, duel solve detection, daily problem generation
├── scheduler.py             # APScheduler job definitions and startup
├── email_service.py         # send_email_otp(), send_duel_invite() via Resend
├── backup.py                # Daily SQLite → S3 backup
├── discord_webhook.py       # Discord notification helpers
├── logger.py                # Structured logging
│
└── migrate_from_dynamo.py   # One-time DynamoDB → SQLite migration script (historical)
```

---

## Database

All data lives in a single SQLite file (default `/data/yeetcode.db`). Schema is defined in `db.py` and applied automatically on startup via `init_db()`. No migrations needed — all `CREATE TABLE` statements use `IF NOT EXISTS`.

### Tables

| Table | Description |
|-------|-------------|
| `users` | Accounts — username, email, XP, streak, group, university |
| `groups` | Study groups — group_id (5-char invite code), leader |
| `daily_problems` | One row per day — LeetCode problem slug, difficulty, tags |
| `daily_completions` | Join table: which user completed which day's problem |
| `bounties` | Time-limited challenges with XP rewards |
| `bounty_progress` | Per-user progress on each bounty |
| `duels` | All duels (PENDING → ACCEPTED → ACTIVE → COMPLETED) |
| `duel_invites` | Shareable invite tokens for non-users (24h expiry) |
| `verification_codes` | OTP codes for email auth (10min expiry) |

### Key design decisions

- **No cache layer** — SQLite in WAL mode is fast enough at this scale. All reads/writes go directly to the DB. This eliminates an entire class of stale-read bugs.
- **Streak is computed from `daily_completions`**, not stored as a static counter, so it's always accurate.
- **Wager duels are symmetric** — both users stake the same amount; no counter-wager negotiation needed.

---

## Background Jobs

| Job | Interval | What it does |
|-----|----------|--------------|
| `update_user_stats` | Every 1 min | Polls LeetCode API for each user's solve counts, updates XP |
| `update_bounty_progress` | Every 5 min | Checks user submissions against active bounties |
| `poll_active_duels` | Every 3 sec | Checks LeetCode submissions for users with active duels |
| `cleanup_expired_duels` | Every 10 min | Deletes expired PENDING duels, resolves timed-out ACTIVE duels |
| `generate_daily_problem` | Daily at midnight UTC | Stores next day's LeetCode daily problem |
| `backup_to_s3` | Daily at 3am UTC | Copies SQLite file to S3 (if `BACKUP_S3_BUCKET` is set) |

---

## Duel Flow

```
create-duel / create-open-challenge
         ↓
     PENDING ──── expires in 1 hour, cleanup job deletes it
         ↓  accept-duel / accept-open-challenge
     ACCEPTED
         ↓  start-duel (each user clicks Start separately, timers are individual)
      ACTIVE ──── verify-duel-solve (user-triggered) or poll_active_duels (auto every 3s)
         ↓  both times recorded
    COMPLETED ──── winner = lower elapsed_ms
```

**XP on completion:**
- Normal: winner +200 XP, loser +25 XP, tie both +200 XP
- Wager: winner gets both wagers + 200 XP bonus, loser loses their wager

---

## Deploying with Coolify

1. Point Coolify at this repo (main branch)
2. Add a **Persistent Storage** volume → mount to `/data`
3. Set env vars (minimum: `YETCODE_API_KEY`, `RESEND_API_KEY`, `SQLITE_PATH=/data/yeetcode.db`)
4. Deploy — `init_db()` creates the database automatically on first boot

---

## Contributing

### Adding an endpoint

All DB logic belongs in an operation class in `aws.py`. Routes in `routes/` are kept thin.

```python
# 1. Add an operation method in aws.py
class DuelOperations:
    @staticmethod
    def my_new_thing(username: str) -> Dict:
        conn = get_db()
        try:
            row = conn.execute("SELECT ...", [username]).fetchone()
            return {"success": True, "data": dict(row)}
        except Exception as e:
            error(f"my_new_thing failed: {e}")
            raise
        finally:
            conn.close()

# 2. Add the route in routes/duels.py
@router.get("/my-new-thing/{username}")
async def my_new_thing_endpoint(username: str, api_key: str = Depends(verify_api_key)):
    try:
        return DuelOperations.my_new_thing(username)
    except Exception as e:
        return {"success": False, "error": str(e)}
```

### Adding a background job

```python
# In background_tasks.py
def my_job():
    ...

# In scheduler.py
scheduler.add_job(my_job, 'interval', minutes=5, id='my_job')
```

### Adding a table

Add a `CREATE TABLE IF NOT EXISTS ...` block to the `SCHEMA_SQL` string in `db.py`. It will be applied on next startup.

### Workflow

1. Fork → create a branch (`git checkout -b feature/your-feature`)
2. Run locally with `uvicorn main:app --reload`
3. Test via `/docs` (Swagger UI)
4. PR against `main`
