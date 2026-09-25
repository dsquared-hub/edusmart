"""Журнал результатов: закрытые темы учеников с итогами проверочных вопросов."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StepAttempt, Topic


@dataclass
class JournalRow:
    topic: Topic
    first_try: int  # вопросов, решённых верно с первой попытки
    mistakes: int  # всего неверных ответов по теме


def _attempt_totals():
    """По каждой теме: сколько верно с первой попытки и сколько ошибок всего."""
    return (
        select(
            StepAttempt.topic_id.label("topic_id"),
            func.sum(
                case((and_(StepAttempt.success, StepAttempt.wrong_count == 0), 1), else_=0)
            ).label("first_try"),
            func.sum(StepAttempt.wrong_count).label("mistakes"),
        )
        .group_by(StepAttempt.topic_id)
        .subquery()
    )


async def completed_entries(
    session: AsyncSession,
    student_ids: list[int],
    *,
    limit: int,
    before_id: int | None = None,
) -> list[JournalRow]:
    """Закрытые темы, новые сверху. before_id — курсор «показать ещё»:
    темы, закрытые раньше указанной (порядок: completed_at, затем id)."""
    if not student_ids:
        return []
    totals = _attempt_totals()
    stmt = (
        select(Topic, totals.c.first_try, totals.c.mistakes)
        .outerjoin(totals, totals.c.topic_id == Topic.id)
        .where(Topic.student_user_id.in_(student_ids), Topic.status == "completed")
        .order_by(desc(Topic.completed_at), desc(Topic.id))
        .limit(limit)
    )
    if before_id is not None:
        cursor_at: datetime | None = await session.scalar(
            select(Topic.completed_at).where(
                Topic.id == before_id, Topic.student_user_id.in_(student_ids)
            )
        )
        if cursor_at is None:
            return []
        stmt = stmt.where(
            or_(
                Topic.completed_at < cursor_at,
                and_(Topic.completed_at == cursor_at, Topic.id < before_id),
            )
        )
    rows = await session.execute(stmt)
    return [
        JournalRow(topic=topic, first_try=int(first or 0), mistakes=int(wrong or 0))
        for topic, first, wrong in rows.all()
    ]


@dataclass
class StudentTotals:
    topics: int
    questions: int
    first_try: int
    topics_since: int


async def student_totals(
    session: AsyncSession, student_ids: list[int], since: datetime
) -> dict[int, StudentTotals]:
    """Итоги по каждому ученику одним запросом: закрыто тем (всего и с `since`),
    вопросов в закрытых темах и сколько из них решено с первой попытки."""
    if not student_ids:
        return {}
    topic_rows = await session.execute(
        select(
            Topic.student_user_id,
            func.count(Topic.id),
            func.sum(case((Topic.completed_at >= since, 1), else_=0)),
        )
        .where(Topic.student_user_id.in_(student_ids), Topic.status == "completed")
        .group_by(Topic.student_user_id)
    )
    attempt_rows = await session.execute(
        select(
            Topic.student_user_id,
            func.count(StepAttempt.id),
            func.sum(
                case((and_(StepAttempt.success, StepAttempt.wrong_count == 0), 1), else_=0)
            ),
        )
        .join(StepAttempt, StepAttempt.topic_id == Topic.id)
        .where(Topic.student_user_id.in_(student_ids), Topic.status == "completed")
        .group_by(Topic.student_user_id)
    )
    result = {sid: StudentTotals(0, 0, 0, 0) for sid in student_ids}
    for sid, topics, since_count in topic_rows.all():
        result[sid].topics = int(topics or 0)
        result[sid].topics_since = int(since_count or 0)
    for sid, questions, first in attempt_rows.all():
        result[sid].questions = int(questions or 0)
        result[sid].first_try = int(first or 0)
    return result
