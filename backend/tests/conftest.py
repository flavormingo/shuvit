"""Tests run against a real Postgres/PostGIS database and Redis, never production.

Needs a local `shuvit_test` database (see `make test-db`).
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

_media_dir = tempfile.mkdtemp(prefix="shuvit-test-media-")
os.environ.update(
    DATABASE_URL="postgresql+asyncpg://shuvit:shuvit@localhost:5432/shuvit_test",
    REDIS_URL="redis://localhost:6379/15",
    MEDIA_DIR=_media_dir,
    RESEND_API_KEY="test",
    JWT_SECRET="test-secret",
    ADMIN_EMAILS="boss@example.com",
    MAGIC_LINK_RATE_LIMIT_SECONDS="0",
)

import pytest
import pytest_asyncio
import resend
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.config import settings
from app.database import async_session
from app.main import app
from app.redis import get_redis

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    for args in (["downgrade", "base"], ["upgrade", "head"]):
        subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=BACKEND_DIR, env=os.environ, check=True, capture_output=True,
        )


@pytest_asyncio.fixture(autouse=True)
async def clean_state():
    async with async_session() as session:
        await session.execute(
            text("TRUNCATE skateparks, users, magic_link_tokens, favorites, media_submissions, media_reports, user_blocks CASCADE")
        )
        await session.commit()
    redis = await get_redis()
    await redis.flushdb()
    yield


@pytest.fixture
def sent_emails(monkeypatch):
    sent: list[dict] = []
    monkeypatch.setattr(resend.Emails, "send", lambda params: sent.append(params))
    return sent


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as c:
        yield c


@pytest_asyncio.fixture
async def park_id():
    async with async_session() as session:
        result = await session.execute(
            text(
                "INSERT INTO skateparks (name, slug, geom, city, state) VALUES "
                "('Test Park', 'test-park', ST_SetSRID(ST_MakePoint(-95.37, 29.76), 4326), 'Houston', 'TX') "
                "RETURNING id"
            )
        )
        await session.commit()
        return str(result.scalar_one())


def otp_from(email: dict) -> str:
    return re.search(r"code: (\d{6})", email["subject"]).group(1)


@pytest.fixture
def login(client, sent_emails):
    """Returns a helper that signs an email in and gives back auth headers."""

    async def _login(email: str) -> dict[str, str]:
        response = await client.post("/auth/request-magic-link", json={"email": email})
        assert response.status_code == 200
        verified = await client.post(
            "/auth/verify-otp", json={"email": email, "code": otp_from(sent_emails[-1])}
        )
        assert verified.status_code == 200
        return {"Authorization": f"Bearer {verified.json()['access_token']}"}

    return _login


@pytest.fixture
def media_dir() -> Path:
    return Path(settings.MEDIA_DIR)
