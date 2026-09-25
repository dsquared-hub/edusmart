"""Дневной лимит объяснений — общий для сайта и бота.

Резервирование атомарное (INSERT … ON CONFLICT DO UPDATE … WHERE), поэтому
одновременные запросы из бота и с сайта не пробьют лимит.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailyUsage
from app.db.session import is_postgres


async def used_today(session: AsyncSession, user_id: int, day: date) -> int:
    return await session.scalar(
        select(DailyUsage.explanations).where(
            DailyUsage.user_id == user_id, DailyUsage.date == day
        )
    ) or 0


async def try_reserve(
    session: AsyncSession, user_id: int, day: date, limit: int, counter: str = "explanations"
) -> bool:
    """+1 к счётчику (explanations | simplifications), если лимит ещё не исчерпан.
    True — место зарезервировано."""
    if limit <= 0:
        return False
    column = getattr(DailyUsage, counter)
    insert = pg_insert if is_postgres(session) else sqlite_insert
    counters = {"explanations": 0, "simplifications": 0, counter: 1}
    stmt = insert(DailyUsage).values(user_id=user_id, date=day, **counters)
    stmt = stmt.on_conflict_do_update(
        index_elements=[DailyUsage.user_id, DailyUsage.date],
        set_={counter: column + 1},
        where=column < limit,
    ).returning(column)
    result = await session.execute(stmt)
    return result.first() is not None


async def refund(
    session: AsyncSession, user_id: int, day: date, counter: str = "explanations"
) -> None:
    """Возвращаем попытку, если объяснение не получилось по нашей вине."""
    column = getattr(DailyUsage, counter)
    await session.execute(
        update(DailyUsage)
        .where(DailyUsage.user_id == user_id, DailyUsage.date == day, column > 0)
        .values({counter: column - 1})
    )
