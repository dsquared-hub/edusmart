"""Тестовый стенд бота: настоящий Dispatcher, поддельный Telegram API, SQLite, заглушка Gemini."""
from __future__ import annotations

import itertools
import os
import tempfile
from datetime import datetime

os.environ.update(
    {
        "BOT_TOKEN": "123456:TEST",
        "GEMINI_FAKE": "1",
        # Проверяем и режим с согласием родителя (по умолчанию он выключен)
        "REQUIRE_PARENT_CONSENT": "1",
        "DEMO_MODE": "0",
        "GEMINI_API_KEY": "",
        "WEB_URL": "https://edu.example.com",
        # Тесты не должны зависеть от настоящего .env
        "OWNER_ID": "999",
        "PRIVACY_POLICY_URL": "",
        "GEMINI_MODEL": "gemini-flash-lite-latest",
        "JWT_SECRET": "test-secret-that-is-long-enough-for-hs256",
        "CHECK_WORKER": "0",
        "MEDIA_DIR": tempfile.mkdtemp(prefix="edu-media-"),
    }
)

import pytest  # noqa: E402
from aiogram import Bot  # noqa: E402
from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.fsm.storage.memory import MemoryStorage  # noqa: E402
from aiogram.types import (  # noqa: E402
    CallbackQuery,
    Chat,
    File,
    Message,
    PhotoSize,
    Update,
)
from aiogram.types import User as TgUser  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db import session as db_session  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.services.explain import ExplainService  # noqa: E402
from app.services.gemini_stub import StubLessonService  # noqa: E402
from bot.app_factory import create_dispatcher  # noqa: E402
from bot.security import SecurityManager  # noqa: E402

_ids = itertools.count(1000)


class MockedSession(BaseSession):
    """Вместо HTTP к Telegram — записываем запросы и отдаём правдоподобные ответы."""

    def __init__(self):
        super().__init__()
        self.requests: list = []

    async def make_request(self, bot, method, timeout=None):
        self.requests.append(method)
        name = type(method).__name__
        if name == "SendMessage":
            return Message(
                message_id=next(_ids),
                date=datetime.now(),
                chat=Chat(id=method.chat_id, type="private"),
                text=method.text,
            )
        if name == "GetFile":
            return File(file_id=method.file_id, file_unique_id="u1", file_path="photos/1.jpg")
        return True

    async def stream_content(self, url, *args, **kwargs):
        yield b"\xff\xd8\xff fake jpeg"

    async def close(self):
        pass

    # --- удобства для проверок ---
    def sent(self, chat_id: int | None = None) -> list:
        return [
            r
            for r in self.requests
            if type(r).__name__ in ("SendMessage", "EditMessageText")
            and (chat_id is None or getattr(r, "chat_id", chat_id) == chat_id)
        ]

    def texts(self, chat_id: int | None = None) -> list[str]:
        return [r.text for r in self.sent(chat_id)]

    def last(self, chat_id: int | None = None):
        return self.sent(chat_id)[-1]

    def alerts(self) -> list[str]:
        return [
            r.text or ""
            for r in self.requests
            if type(r).__name__ == "AnswerCallbackQuery"
        ]


class Harness:
    def __init__(self, dp, bot, session, explain):
        self.dp, self.bot, self.api, self.explain = dp, bot, session, explain

    def _tg_user(self, uid: int, name: str, lang: str | None = None) -> TgUser:
        return TgUser(id=uid, is_bot=False, first_name=name, username=f"u{uid}", language_code=lang)

    async def send(self, uid: int, text: str | None = None, *, photo: bool = False,
                   caption: str | None = None, name: str = "Аня",
                   chat_type: str = "private", lang: str | None = None) -> None:
        message = Message(
            message_id=next(_ids),
            date=datetime.now(),
            chat=Chat(id=uid if chat_type == "private" else -uid, type=chat_type),
            from_user=self._tg_user(uid, name, lang),
            text=text,
            caption=caption,
            photo=[PhotoSize(file_id="p1", file_unique_id="pu1", width=10, height=10)]
            if photo
            else None,
        )
        await self._feed(Update(update_id=next(_ids), message=message))

    async def press(self, uid: int, data: str, name: str = "Аня") -> None:
        message = Message(
            message_id=next(_ids),
            date=datetime.now(),
            chat=Chat(id=uid, type="private"),
            text="…",
        )
        query = CallbackQuery(
            id=str(next(_ids)),
            from_user=self._tg_user(uid, name),
            chat_instance="ci",
            data=data,
            message=message,
        )
        await self._feed(Update(update_id=next(_ids), callback_query=query))

    async def _feed(self, update: Update) -> None:
        update = Update.model_validate(update.model_dump(), context={"bot": self.bot})
        await self.dp.feed_update(self.bot, update)

    def buttons(self, request) -> list:
        markup = getattr(request, "reply_markup", None)
        if markup is None:
            return []
        return [b for row in markup.inline_keyboard for b in row]

    def callback_data(self, request) -> list[str]:
        return [b.callback_data for b in self.buttons(request) if b.callback_data]


# TEST_DATABASE_URL=postgresql+asyncpg://… — прогнать тесты на настоящем PostgreSQL
PG_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture
async def db(tmp_path):
    engine = db_session.init_db(PG_URL or f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as conn:
        if PG_URL:  # общая база — чистим перед каждым тестом
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await db_session.dispose_db()


OWNER = 999


@pytest.fixture
def settings():
    # Сценарии жмут кнопки быстрее человека — анти-флуд проверяется отдельно.
    return get_settings().model_copy(
        update={"daily_explain_limit": 20, "owner_id": OWNER, "flood_max_messages": 10_000}
    )


_dispatcher = None


@pytest.fixture
async def h(db, settings):
    # Роутеры — модульные синглтоны, их можно подключить к Dispatcher только раз.
    global _dispatcher
    explain = ExplainService(StubLessonService(), settings)
    if _dispatcher is None:
        _dispatcher = create_dispatcher(explain, settings)
    dp = _dispatcher
    dp["explain"], dp["settings"] = explain, settings
    dp["security"] = SecurityManager(owner_id=OWNER)
    dp.fsm.storage = MemoryStorage()
    api = MockedSession()
    bot = Bot(token=settings.bot_token, session=api)
    yield Harness(dp, bot, api, explain)
