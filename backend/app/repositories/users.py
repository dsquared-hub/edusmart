from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_by_telegram(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def get_by_login(session: AsyncSession, login: str) -> User | None:
    return await session.scalar(select(User).where(User.login == login.lower()))


async def upsert_telegram_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None = None,
    full_name: str | None = None,
    lang: str | None = None,
) -> User:
    """Находит пользователя по Telegram ID или создаёт его; обновляет имя.

    lang — язык только для НОВОГО пользователя (потом его меняют в профиле).
    """
    user = await get_by_telegram(session, telegram_id)
    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            lang=lang or "ru",
        )
        session.add(user)
        await session.flush()
        return user
    if username and user.username != username:
        user.username = username
    # Взрослый указывает имя при регистрации в боте — имя из Telegram его не перезаписывает
    if full_name and user.full_name != full_name and (user.role not in ("parent", "teacher") or not user.full_name):
        user.full_name = full_name
    return user


async def login_exists(session: AsyncSession, login: str) -> bool:
    return await session.scalar(select(User.id).where(User.login == login)) is not None
