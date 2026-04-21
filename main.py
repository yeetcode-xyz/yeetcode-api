#!/usr/bin/env python3
"""
FastAPI server for YeetCode
"""

import os
import sys
import argparse
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Parse command line arguments for environment selection
parser = argparse.ArgumentParser(description='YeetCode FastAPI Server')
parser.add_argument('--env', type=str, default='prod', choices=['prod', 'dev'],
                    help='Environment to run (prod or dev)')
args, unknown = parser.parse_known_args()

# Load environment-specific .env file
env_file = f'.env.{args.env}'
if os.path.exists(env_file):
    load_dotenv(env_file)
    print(f"✅ Loaded environment from {env_file}")
else:
    load_dotenv()
    print(f"⚠️ {env_file} not found, using default .env")

# Import routers
from routes.auth import router as auth_router
from routes.users import router as users_router
from routes.groups import router as groups_router
from routes.daily import router as daily_router
from routes.bounties import router as bounties_router
from routes.duels import router as duels_router
from routes.admin import router as admin_router
from routes.push import router as push_router
from routes.blitz import router as blitz_router
from routes.roadmap import router as roadmap_router

from aws import DuelOperations, VerificationOperations
from logger import debug, info, warning, error
from scheduler import start_scheduler, stop_scheduler, get_scheduler_status, trigger_job_manually
from db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    # Startup
    info("🚀 Starting FastAPI server with SQLite backend")

    # 1. Initialize SQLite schema (idempotent)
    info("🗄️ Initializing SQLite database...")
    init_db()
    info("✅ SQLite database ready")

    # 2. Start the APScheduler for background jobs
    start_scheduler()

    # 3. Start background monitoring tasks
    duel_task    = asyncio.create_task(monitor_active_duels())
    cleanup_task = asyncio.create_task(cleanup_expired_codes_task())

    info("✅ FastAPI server started successfully")

    yield

    # Shutdown
    info("🛑 Shutting down FastAPI server...")
    stop_scheduler()
    duel_task.cancel()
    cleanup_task.cancel()
    info("✅ FastAPI server shutdown complete")


app = FastAPI(
    title="YeetCode API",
    description="YeetCode backend — SQLite-powered",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

PORT_STR = os.getenv("PORT")
if not PORT_STR:
    raise ValueError("PORT environment variable is required")
PORT = int(PORT_STR)

HOST = "0.0.0.0"

# Include routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(groups_router)
app.include_router(daily_router)
app.include_router(bounties_router)
app.include_router(duels_router)
app.include_router(admin_router)
app.include_router(push_router)
app.include_router(blitz_router)
app.include_router(roadmap_router)

if DEBUG_MODE:
    print("[DEBUG] Registered routes:")
    for route in app.routes:
        if hasattr(route, 'path'):
            print(f"  {route.methods} {route.path}")


@app.get("/")
async def root():
    return {"message": "YeetCode API is running", "timestamp": datetime.now().isoformat()}


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "environment": args.env,
        "port": PORT,
        "timestamp": datetime.now().isoformat(),
    }


async def monitor_active_duels():
    """Background task to monitor active duels for timeouts."""
    info("Starting duel monitoring background task")
    while True:
        try:
            result = await asyncio.to_thread(DuelOperations.handle_duel_timeouts)
            if result.get("completed_duels", 0) > 0:
                info(f"⏱️ Duel monitor: completed {result['completed_duels']} timed-out duels")
        except Exception as e:
            error(f"Duel monitoring error: {e}")
        await asyncio.sleep(30)


async def cleanup_expired_codes_task():
    """Background task to clean up expired verification codes every 5 minutes."""
    debug("Starting cleanup expired codes background task")
    while True:
        try:
            result = VerificationOperations.cleanup_expired_codes()
            if result.get("count", 0) > 0:
                info(f"Cleaned up {result.get('count', 0)} expired verification codes")
        except Exception as e:
            error(f"Cleanup expired codes error: {e}")
        await asyncio.sleep(5 * 60)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
