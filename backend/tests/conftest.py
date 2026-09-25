from __future__ import annotations

import os
import tempfile

os.environ.update(
    {
        "BOT_TOKEN": "123456:TEST-TOKEN",
        "BOT_USERNAME": "edu_test_bot",
        "GEMINI_FAKE": "1",
        # Проверяем и режим с согласием родителя (по умолчанию он выключен)
        "REQUIRE_PARENT_CONSENT": "1",
        "DEMO_MODE": "0",
        "GEMINI_API_KEY": "",
        "JWT_SECRET": "test-secret-that-is-long-enough-for-hs256",
        "WEB_URL": "https://edu.example.com",
        "OWNER_ID": "",
        "PRIVACY_POLICY_URL": "",
        # Лимиты частоты проверяются отдельным тестом со своим приложением
        "RATE_LIMIT_AUTH": "0",
        "RATE_LIMIT_EXPLAIN": "0",
        "RATE_LIMIT_API": "0",
        # Проверка работ: обработчик в тестах вызываем вручную, файлы — во временную папку
        "CHECK_WORKER": "0",
        "PUSH_WORKER": "0",
        "VAPID_PUBLIC_KEY": "",
        "VAPID_PRIVATE_KEY": "",
        "MEDIA_DIR": tempfile.mkdtemp(prefix="edu-media-"),
    }
)

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db import session as db_session  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.services.explain import ExplainService  # noqa: E402
from app.services.gemini_stub import StubLessonService  # noqa: E402


# TEST_DATABASE_URL=postgresql+asyncpg://… — прогнать тесты на настоящем PostgreSQL
PG_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture
def db_url(tmp_path) -> str:
    return PG_URL or f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
async def db(db_url):
    engine = db_session.init_db(db_url)
    async with engine.begin() as conn:
        if PG_URL:  # общая база — чистим перед каждым тестом
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await db_session.dispose_db()


@pytest.fixture
async def client(db):
    """HTTP-клиент к API с заглушкой Gemini."""
    settings = get_settings().model_copy(update={"daily_explain_limit": 20})
    app.state.explain = ExplainService(StubLessonService(), settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
