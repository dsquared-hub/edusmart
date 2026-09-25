"""Журнал результатов для родителя и учителя — общий для сайта и бота.

Родитель видит своих детей, учитель — привязанных учеников. В журнал попадает
каждая закрытая тема: когда, сколько вопросов, сколько верно с первой попытки,
сколько ошибок и очков.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import utcnow
from app.db.models import Student, User
from app.repositories import journal as journal_repo
from app.repositories.students import get_children, get_teacher_students, weak_topics

PAGE_SIZE = 30
MAX_PAGE_SIZE = 100
WEEK = timedelta(days=7)


class JournalError(Exception):
    def __init__(self, code: str, status: int):
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass
class StudentSummary:
    id: int
    name: str
    grade: int | None
    points: int
    streak: int
    last_active_on: date | None
    topics_completed: int
    topics_week: int
    questions: int
    first_try: int
    weak: list[tuple[str, int]] = field(default_factory=list)

    @property
    def accuracy(self) -> int | None:
        """Доля вопросов, решённых с первой попытки, в процентах."""
        return round(100 * self.first_try / self.questions) if self.questions else None


@dataclass
class JournalEntry:
    topic_id: int
    student_id: int
    student_name: str
    title: str
    subject: str | None
    source: str
    completed_at: datetime  # наивное UTC, как в БД
    questions: int
    first_try: int
    mistakes: int
    points: int


@dataclass
class Journal:
    students: list[StudentSummary]
    entries: list[JournalEntry]
    has_more: bool


async def linked_students(session: AsyncSession, viewer: User) -> list[tuple[Student, User]]:
    """Ученики, чьи результаты может видеть этот пользователь."""
    if viewer.role == "parent":
        students = await get_children(session, viewer.id)
    elif viewer.role == "teacher":
        students = await get_teacher_students(session, viewer.id)
    else:
        raise JournalError("not_parent_or_teacher", 403)
    if not students:
        return []
    users = {
        u.id: u
        for u in await session.scalars(
            select(User).where(User.id.in_([s.user_id for s in students]))
        )
    }
    return [(s, users[s.user_id]) for s in students if s.user_id in users]


async def build_journal(
    session: AsyncSession,
    viewer: User,
    *,
    student_id: int | None = None,
    limit: int = PAGE_SIZE,
    before_id: int | None = None,
    with_weak: bool = True,
) -> Journal:
    linked = await linked_students(session, viewer)
    if student_id is not None:
        linked = [(s, u) for s, u in linked if s.user_id == student_id]
        if not linked:
            # Не различаем «нет такого» и «чужой ученик» — не раскрываем чужие id
            raise JournalError("student_not_found", 404)
    ids = [s.user_id for s, _ in linked]
    names = {u.id: u.display_name for _, u in linked}

    totals = await journal_repo.student_totals(session, ids, utcnow() - WEEK)
    summaries = []
    for student, user in linked:
        total = totals.get(student.user_id)
        summaries.append(
            StudentSummary(
                id=student.user_id,
                name=user.display_name,
                grade=student.grade,
                points=student.points,
                streak=student.streak,
                last_active_on=student.last_active_on,
                topics_completed=total.topics if total else 0,
                topics_week=total.topics_since if total else 0,
                questions=total.questions if total else 0,
                first_try=total.first_try if total else 0,
                weak=await weak_topics(session, student.user_id, limit=3) if with_weak else [],
            )
        )

    limit = max(1, min(limit, MAX_PAGE_SIZE))
    # +1 строка — чтобы узнать, есть ли следующая страница, без отдельного COUNT
    rows = await journal_repo.completed_entries(
        session, ids, limit=limit + 1, before_id=before_id
    )
    entries = [
        JournalEntry(
            topic_id=row.topic.id,
            student_id=row.topic.student_user_id,
            student_name=names.get(row.topic.student_user_id, "—"),
            title=row.topic.title or "",
            subject=row.topic.subject,
            source=row.topic.source,
            completed_at=row.topic.completed_at or row.topic.updated_at,
            questions=row.topic.total_steps,
            first_try=row.first_try,
            mistakes=row.mistakes,
            points=row.topic.points_earned,
        )
        for row in rows[:limit]
    ]
    return Journal(students=summaries, entries=entries, has_more=len(rows) > limit)
