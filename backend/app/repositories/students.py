from __future__ import annotations

import secrets
from datetime import date, datetime

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ActivityDay,
    ParentLink,
    StepAttempt,
    Student,
    TeacherLink,
    Topic,
    User,
)


# ---------- Ученики ----------

async def _generate_family_code(session: AsyncSession) -> str:
    for _ in range(1000):
        code = f"{secrets.randbelow(1_000_000):06d}"
        taken = await session.scalar(
            select(Student.user_id).where(Student.family_code == code)
        )
        if not taken:
            return code
    raise RuntimeError("Не удалось сгенерировать уникальный код")


async def get_student(session: AsyncSession, user_id: int) -> Student | None:
    return await session.get(Student, user_id)


async def get_student_by_code(session: AsyncSession, code: str) -> Student | None:
    return await session.scalar(select(Student).where(Student.family_code == code))


async def create_student(
    session: AsyncSession,
    user_id: int,
    *,
    consent: bool = False,
    grade: int | None = None,
) -> Student:
    student = Student(
        user_id=user_id,
        family_code=await _generate_family_code(session),
        consent_confirmed=consent,
        grade=grade,
        points=0,
        streak=0,
    )
    session.add(student)
    await session.flush()
    return student


# ---------- Привязки ----------

async def is_linked_parent(session: AsyncSession, parent_id: int, student_id: int) -> bool:
    return await session.scalar(
        select(ParentLink.id).where(
            ParentLink.parent_user_id == parent_id,
            ParentLink.student_user_id == student_id,
        )
    ) is not None


async def link_parent(session: AsyncSession, parent_id: int, student_id: int) -> bool:
    """True — привязка создана, False — уже была."""
    if await is_linked_parent(session, parent_id, student_id):
        return False
    session.add(ParentLink(parent_user_id=parent_id, student_user_id=student_id))
    await session.flush()
    return True


async def is_linked_teacher(session: AsyncSession, teacher_id: int, student_id: int) -> bool:
    return await session.scalar(
        select(TeacherLink.id).where(
            TeacherLink.teacher_user_id == teacher_id,
            TeacherLink.student_user_id == student_id,
        )
    ) is not None


async def link_teacher(session: AsyncSession, teacher_id: int, student_id: int) -> bool:
    if await is_linked_teacher(session, teacher_id, student_id):
        return False
    session.add(TeacherLink(teacher_user_id=teacher_id, student_user_id=student_id))
    await session.flush()
    return True


async def get_children(session: AsyncSession, parent_id: int) -> list[Student]:
    rows = await session.scalars(
        select(Student)
        .join(ParentLink, ParentLink.student_user_id == Student.user_id)
        .where(ParentLink.parent_user_id == parent_id)
        .order_by(Student.created_at)
    )
    return list(rows)


async def get_parents_of(session: AsyncSession, student_id: int) -> list[User]:
    rows = await session.scalars(
        select(User)
        .join(ParentLink, ParentLink.parent_user_id == User.id)
        .where(ParentLink.student_user_id == student_id)
    )
    return list(rows)


async def get_teachers_of(session: AsyncSession, student_id: int) -> list[User]:
    rows = await session.scalars(
        select(User)
        .join(TeacherLink, TeacherLink.teacher_user_id == User.id)
        .where(TeacherLink.student_user_id == student_id)
    )
    return list(rows)


async def get_teacher_students(session: AsyncSession, teacher_id: int) -> list[Student]:
    rows = await session.scalars(
        select(Student)
        .join(TeacherLink, TeacherLink.student_user_id == Student.user_id)
        .where(TeacherLink.teacher_user_id == teacher_id)
        .order_by(Student.created_at)
    )
    return list(rows)


# ---------- Статистика ----------

async def completed_count(session: AsyncSession, student_id: int) -> int:
    return await session.scalar(
        select(func.count(Topic.id)).where(
            Topic.student_user_id == student_id, Topic.status == "completed"
        )
    ) or 0


async def topics_completed_since(
    session: AsyncSession, student_id: int, since: datetime
) -> list[Topic]:
    rows = await session.scalars(
        select(Topic).where(
            Topic.student_user_id == student_id,
            Topic.status == "completed",
            Topic.completed_at >= since,
        )
    )
    return list(rows)


async def activity_days_between(
    session: AsyncSession, student_id: int, start: date, end: date
) -> int:
    return await session.scalar(
        select(func.count(ActivityDay.id)).where(
            ActivityDay.user_id == student_id,
            ActivityDay.date >= start,
            ActivityDay.date <= end,
        )
    ) or 0


async def weak_topics(
    session: AsyncSession, student_id: int, limit: int = 5
) -> list[tuple[str, int]]:
    """Темы, где ученик чаще всего ошибался (по сумме неверных ответов)."""
    total = func.sum(StepAttempt.wrong_count).label("total")
    rows = await session.execute(
        select(Topic.title, total)
        .join(StepAttempt, StepAttempt.topic_id == Topic.id)
        .where(Topic.student_user_id == student_id, Topic.status == "completed")
        .group_by(Topic.id, Topic.title)
        .order_by(desc(total))
        .limit(limit)
    )
    return [(r.title, r.total) for r in rows.all() if r.total]


async def mark_activity_day(session: AsyncSession, user_id: int, day: date) -> None:
    exists = await session.scalar(
        select(ActivityDay.id).where(ActivityDay.user_id == user_id, ActivityDay.date == day)
    )
    if not exists:
        session.add(ActivityDay(user_id=user_id, date=day))
