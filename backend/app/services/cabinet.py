"""Кабинеты родителя и учителя: короткая сводка для бота и сайта.

Родитель — по каждому своему ребёнку: очки, серия, темы за неделю, точность и
вечерний тест сегодня. Учитель — по классу целиком и работы, ждущие проверки.
Ученики — только привязанные (те же правила, что у журнала).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import local_now
from app.db.models import DailyTest, User, WorkCheck
from app.services import readiness
from app.services.journal import StudentSummary, build_journal
from app.services.parent_day import study_week

WEAK_TOPICS = 3


@dataclass
class EveningToday:
    status: str  # active | finished
    score: int
    total: int


@dataclass
class ChildCard:
    summary: StudentSummary
    evening: EveningToday | None
    week: list[dict] = field(default_factory=list)  # 🟢/🟡/🔴 по дням (parent_day.study_week)
    readiness: list[tuple[str, int | None]] = field(default_factory=list)  # (предмет, ERS %)


@dataclass
class ClassSummary:
    students: int
    active_today: int
    topics_week: int
    accuracy: int | None
    checks_to_review: int
    weak: list[tuple[str, int]] = field(default_factory=list)


async def _evening_today(session: AsyncSession, ids: list[int], today: date) -> dict[int, EveningToday]:
    if not ids:
        return {}
    tests = await session.scalars(
        select(DailyTest).where(DailyTest.student_id.in_(ids), DailyTest.date == today)
    )
    return {t.student_id: EveningToday(t.status, t.score, len(t.slots or [])) for t in tests}


def _subject_name(subject, lang: str) -> str:
    return {"uz": subject.name_uz, "en": subject.name_en}.get(lang, subject.name_ru)


async def parent_cabinet(session: AsyncSession, parent: User) -> list[ChildCard]:
    journal = await build_journal(session, parent, limit=1)
    ids = [s.id for s in journal.students]
    today = local_now().date()
    evening = await _evening_today(session, ids, today)
    weeks = await study_week(session, ids, today)
    cards = []
    for s in journal.students:
        ers = [(_subject_name(subject, parent.lang), row.score) for subject, row in await readiness.latest(session, s.id)]
        cards.append(ChildCard(s, evening.get(s.id), weeks.get(s.id, []), ers))
    return cards


async def teacher_cabinet(session: AsyncSession, teacher: User) -> ClassSummary:
    journal = await build_journal(session, teacher, limit=1)
    students = journal.students
    today = local_now().date()
    questions = sum(s.questions for s in students)
    first_try = sum(s.first_try for s in students)
    weak: dict[str, int] = {}
    for s in students:
        for title, mistakes in s.weak:
            weak[title] = weak.get(title, 0) + mistakes
    checks = await session.scalar(
        select(func.count()).select_from(WorkCheck).where(
            WorkCheck.teacher_user_id == teacher.id, WorkCheck.status == "review"
        )
    )
    return ClassSummary(
        students=len(students),
        active_today=sum(s.last_active_on == today for s in students),
        topics_week=sum(s.topics_week for s in students),
        accuracy=round(first_try * 100 / questions) if questions else None,
        checks_to_review=checks or 0,
        weak=sorted(weak.items(), key=lambda kv: -kv[1])[:WEAK_TOPICS],
    )
