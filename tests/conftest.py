import os
import tempfile

# Set required env vars BEFORE any app module is imported.
# main.py reads PORT at module level and raises ValueError if missing.
# db.py reads SQLITE_PATH at module level to set DB_PATH.
_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_db_file.close()

os.environ["SQLITE_PATH"] = _db_file.name
os.environ.setdefault("PORT", "6969")
os.environ.setdefault("YEETCODE_API_KEY", "test-api-key")
os.environ.setdefault("RESEND_API_KEY", "fake")
os.environ.setdefault("GEMINI_API_KEY", "fake")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_fake")
os.environ.setdefault("VAPID_PRIVATE_KEY", "fake")
os.environ.setdefault("VAPID_PUBLIC_KEY", "fake")
os.environ.setdefault("DISCORD_WEBHOOK_URL", "")
os.environ.setdefault("DISCORD_OTP_WEBHOOK_URL", "")
os.environ.setdefault("DEBUG_MODE", "false")

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    """Session-scoped TestClient with scheduler and external calls patched out."""
    with (
        patch("scheduler.start_scheduler"),
        patch("scheduler.stop_scheduler"),
        patch("email_service._post_discord"),
        patch("discord_webhook.requests.post", return_value=MagicMock(status_code=204)),
    ):
        from main import app
        with TestClient(app) as c:
            yield c


@pytest.fixture(scope="session")
def auth_headers():
    return {"Authorization": f"Bearer {os.environ['YEETCODE_API_KEY']}"}
