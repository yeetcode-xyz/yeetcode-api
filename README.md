# YeetCode API

FastAPI backend for [YeetCode](https://github.com/yeetcode-xyz/yeetcode-app) - Competitive Programming Practice App.

## Overview

This is the backend API that powers YeetCode, a desktop application for competitive programming practice. It provides endpoints for user authentication, study groups, duels, daily challenges, and leaderboards.

## Features

- 🔐 **Magic Link Authentication** - Email-based verification with 6-digit codes
- 👥 **Study Groups** - Create/join groups with invite codes and track group leaderboards
- ⚔️ **Duel System** - Real-time competitive coding challenges between users
- 📅 **Daily Challenges** - LeetCode daily problem tracking with XP rewards
- 🎯 **Bounty System** - Time-limited coding challenges with rewards
- 📊 **Progress Tracking** - XP, streaks, and comprehensive leaderboards
- ⚡ **Cache-First Architecture** - Write-Ahead Log (WAL) with DynamoDB persistence

## Tech Stack

- **FastAPI** - Modern, fast web framework for Python
- **AWS DynamoDB** - NoSQL database for data persistence
- **Resend** - Email service for magic link authentication
- **APScheduler** - Background task scheduler
- **Redis-like Cache** - In-memory cache with WAL for performance

## Setup

### Prerequisites

- Python 3.10+
- AWS account with DynamoDB access
- Resend API key for email services

### Installation

```bash
# Clone the repository
git clone https://github.com/yeetcode-xyz/yeetcode-api.git
cd yeetcode-api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables template
cp .env.example .env
# Edit .env with your actual credentials
```

### Environment Variables

See [.env.example](.env.example) for required environment variables:
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` - AWS credentials
- `RESEND_API_KEY` - Email service API key
- `YEETCODE_API_KEY` - API authentication key
- Database table names and Discord webhook URLs

### Running the Server

```bash
# Development
uvicorn main:app --reload --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Project Structure

```
.
├── main.py                 # FastAPI application entry point
├── routes/                 # API route handlers
│   ├── auth.py            # Authentication endpoints
│   ├── groups.py          # Study group management
│   ├── duels.py           # Duel system
│   ├── daily.py           # Daily challenges
│   ├── bounties.py        # Bounty system
│   ├── users.py           # User management
│   └── admin.py           # Admin utilities
├── cache_manager.py       # In-memory cache with WAL
├── cache_operations.py    # Cache CRUD operations
├── wal_manager.py         # Write-Ahead Log manager
├── aws.py                 # DynamoDB operations
├── auth.py                # Authentication utilities
├── email_service.py       # Email sending service
├── discord_webhook.py     # Discord notifications
├── background_tasks.py    # Scheduled background jobs
├── scheduler.py           # APScheduler configuration
└── logger.py              # Logging configuration
```

## Key Features

### Cache-First Architecture

The API uses a cache-first approach with Write-Ahead Logging (WAL):
1. All writes go to in-memory cache first
2. Operations are logged in WAL for crash recovery
3. Background process asynchronously persists to DynamoDB
4. Provides low-latency reads and atomic operations

### Magic Link Authentication

Users authenticate via email with 6-digit verification codes:
1. User enters email
2. System sends verification code
3. User verifies with code
4. JWT-like session token issued

### Duel System

Real-time competitive coding:
- Create/accept duel challenges
- Track problem solving in real-time
- XP rewards for winners
- Leaderboard integration

## Contributing

This repository is part of the YeetCode project. See the [main repository](https://github.com/yeetcode-xyz/yeetcode-app) for contribution guidelines.

## License

MIT License - see [LICENSE](LICENSE) file for details

## Related Repositories

- [yeetcode-app](https://github.com/yeetcode-xyz/yeetcode-app) - Electron desktop application (frontend)

---

Built with ❤️ by the YeetCode team
