from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StepAttempt, Topic


async def get_topic(
    session: AsyncSession, topic_id: int, *, for_update: bool = False
) -> Topic | None:
    stmt = select(Topic).where(Topic.id == topic_id)
    if for_update:
        # PostgreSQL: блокируем строку, чтобы бот и сайт не засчитали шаг дважды
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def create_topic(
    session: AsyncSession,
    *,
    student_user_id: int,
    title: str,
    steps: list[dict],
    subject: str | None,
    grade: int | None,
    source: str,
) -> Topic:
    topic = Topic(
        student_user_id=student_user_id,
        title=title,
        steps=steps,
        subject=subject,
        grade=grade,
        source=source,
        status="in_progress",
        current_step=0,
        wrong_count=0,
        points_earned=0,
    )
    session.add(topic)
    await session.flush()
    return topic


async def list_in_progress(
    session: AsyncSession, student_user_id: int, limit: int = 5
) -> list[Topic]:
    rows = await session.scalars(
        select(Topic)
        .where(Topic.student_user_id == student_user_id, Topic.status == "in_progress")
        .order_by(desc(Topic.updated_at))
        .limit(limit)
    )
    return list(rows)


async def list_completed(
    session: AsyncSession, student_user_id: int, limit: int = 10
) -> list[Topic]:
    rows = await session.scalars(
        select(Topic)
        .where(Topic.student_user_id == student_user_id, Topic.status == "completed")
        .order_by(desc(Topic.completed_at))
        .limit(limit)
    )
    return list(rows)


async def record_attempt(
    session: AsyncSession,
    topic_id: int,
    step_index: int,
    *,
    success: bool,
    wrong_count: int = 0,
) -> None:
    session.add(
        StepAttempt(
            topic_id=topic_id,
            step_index=step_index,
            wrong_count=wrong_count,
            success=success,
        )
    )
