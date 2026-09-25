from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import utcnow
from app.db.models import Event
from app.db.session import is_postgres


async def enqueue(session: AsyncSession, type_: str, payload: dict) -> Event:
    event = Event(type=type_, payload=payload)
    session.add(event)
    await session.flush()
    return event


async def fetch_pending(session: AsyncSession, limit: int = 50) -> list[Event]:
    """Необработанные события. В PostgreSQL строки блокируются до commit
    (SKIP LOCKED) — несколько экземпляров бота не отправят сообщение дважды."""
    stmt = (
        select(Event)
        .where(Event.processed_at.is_(None))
        .order_by(Event.id)
        .limit(limit)
    )
    if is_postgres(session):
        stmt = stmt.with_for_update(skip_locked=True)
    return list(await session.scalars(stmt))


def mark_processed(event: Event) -> None:
    event.processed_at = utcnow()
