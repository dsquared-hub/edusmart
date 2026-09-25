"""Бан-лист владельца бота (по Telegram ID)."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BlockedUser, Student, User


async def is_blocked(session: AsyncSession, telegram_id: int | None) -> bool:
    if telegram_id is None:
        return False
    return await session.get(BlockedUser, telegram_id) is not None


async def block_user(session: AsyncSession, telegram_id: int, reason: str | None = None) -> bool:
    """True — блокировка создана, False — уже была."""
    if await session.get(BlockedUser, telegram_id) is not None:
        return False
    session.add(BlockedUser(telegram_id=telegram_id, reason=reason))
    await session.flush()
    return True


async def unblock_user(session: AsyncSession, telegram_id: int) -> bool:
    """True — блокировка снята, False — её не было."""
    banned = await session.get(BlockedUser, telegram_id)
    if banned is None:
        return False
    await session.delete(banned)
    await session.flush()
    return True


async def blocked_ids(session: AsyncSession) -> set[int]:
    return set(await session.scalars(select(BlockedUser.telegram_id)))


async def count_users(session: AsyncSession) -> int:
    return await session.scalar(select(func.count(User.id))) or 0


async def count_students(session: AsyncSession) -> int:
    return await session.scalar(select(func.count(Student.user_id))) or 0
