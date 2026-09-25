"""Async-подключение к БД. Один движок на процесс (API или бот).

    async with SessionLocal() as session:
        ...
        await session.commit()
"""
from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_db(url: str | None = None) -> AsyncEngine:
    """Создаёт движок. Повторный вызов с другим URL пересоздаёт его (тесты)."""
    global _engine, _sessionmaker
    url = url or get_settings().async_database_url
    is_sqlite = url.startswith("sqlite")
    kwargs = {} if is_sqlite else {"pool_pre_ping": True}
    _engine = create_async_engine(url, **kwargs)

    if is_sqlite:

        @event.listens_for(_engine.sync_engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            # Бот и API пишут в один файл из разных процессов: WAL + ожидание
            # вместо мгновенной ошибки «database is locked».
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, autoflush=False)
    return _engine


def SessionLocal() -> AsyncSession:  # noqa: N802 — привычное имя фабрики
    if _sessionmaker is None:
        init_db()
    return _sessionmaker()


async def dispose_db() -> None:
    if _engine is not None:
        await _engine.dispose()


def is_postgres(session: AsyncSession) -> bool:
    return session.get_bind().dialect.name == "postgresql"
