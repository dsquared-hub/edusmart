"""Отчёт родителю (Модуль 4, п. 2.3) и задания ребёнку.

Светофор освоения тем (зелёный 80%+, жёлтый 50–79%, красный <50%), динамика за
неделю и месяц, аккуратность письменных работ (из проверки фото, Модуль 5),
Exam Readiness Score с советом и «Прислать ребёнку задание» по слабой теме.
Доступ — только к своим детям (родитель) или своим ученикам (учитель).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.timeutil import local_today, utcnow
from app.db.models import (
    Assignment, Attempt, CurriculumSubject, CurriculumTopic, DailyTest, Student, User, WorkCheckItem,
)
from app.repositories import events as events_repo
from app.repositories.students import is_linked_parent, is_linked_teacher
from app.services import evening, readiness

EVENT_ASSIGNMENT_NEW = "assignment_new"  # задание ребёнку — в бот


class ReportError(Exception):
    def __init__(self, code: str, status: int = 403):
        super().__init__(code)
        self.code = code
        self.status = status


async def ensure_can_view(session: AsyncSession, viewer: User, student_id: int) -> Student:
    """Сам ученик, его родитель или учитель. Чужой ребёнок неотличим от несуществующего."""
    student = await session.get(Student, student_id)
    allowed = student is not None and (
        viewer.id == student_id
        or (viewer.role == "parent" and await is_linked_parent(session, viewer.id, student_id))
        or (viewer.role == "teacher" and await is_linked_teacher(session, viewer.id, student_id))
    )
    if not allowed:
        raise ReportError("student_not_found", 404)
    return student


def light(accuracy: float | None) -> str | None:
    if accuracy is None:
        return None
    return "green" if accuracy >= 0.8 else "yellow" if accuracy >= 0.5 else "red"


def _name(obj, lang: str) -> str:
    return {"uz": obj.name_uz, "en": obj.name_en}.get(lang, obj.name_ru)


async def readiness_view(session: AsyncSession, student_id: int, lang: str) -> list[dict]:
    out = []
    for subject, row in await readiness.latest(session, student_id):
        advice_ids = row.components.get("advice", [])
        topics = {t.id: t for t in await session.scalars(select(CurriculumTopic).where(CurriculumTopic.id.in_(advice_ids)))}
        out.append({
            "subject_id": subject.id,
            "subject": _name(subject, lang),
            "grade": subject.grade,
            "score": row.score,  # None — «Недостаточно данных»
            "components": {k: row.components[k] for k in ("M", "S", "V", "R") if k in row.components},
            "attempts": row.components.get("attempts", 0),
            "min_attempts": row.components.get("min_attempts"),
            "advice": [{"id": i, "name": _name(topics[i], lang)} for i in advice_ids if i in topics],
            "history": [
                {"score": h.score, "at": h.calculated_at.isoformat() + "Z"}
                for h in await readiness.history(session, student_id, subject.id)
                if h.score is not None
            ],
        })
    return out


async def report(session: AsyncSession, viewer: User, student_id: int) -> dict:
    student = await ensure_can_view(session, viewer, student_id)
    lang = viewer.lang if viewer.lang in ("ru", "uz", "en") else "ru"
    tz = ZoneInfo(get_settings().timezone)
    today = local_today()

    # Светофор: последние 5 ответов по каждой теме, где ученик уже отвечал
    topic_ids = list(await session.scalars(select(Attempt.topic_id).where(Attempt.student_id == student_id).distinct()))
    topics = list(await session.scalars(select(CurriculumTopic).where(CurriculumTopic.id.in_(topic_ids)).order_by(CurriculumTopic.order)))
    subjects = {s.id: s for s in await session.scalars(select(CurriculumSubject).where(CurriculumSubject.id.in_({t.subject_id for t in topics})))}
    lights = []
    for m in await readiness.topic_mastery(session, student_id, topics):
        lights.append({
            "topic_id": m.topic.id,
            "topic": _name(m.topic, lang),
            "subject": _name(subjects[m.topic.subject_id], lang) if m.topic.subject_id in subjects else "",
            "accuracy": None if m.accuracy is None else round(m.accuracy * 100),
            "light": light(m.accuracy),
        })
    lights.sort(key=lambda x: (x["accuracy"] if x["accuracy"] is not None else 101))

    # Динамика: ответы и верные по дням (по Ташкенту) за 30 дней
    since = utcnow() - timedelta(days=31)
    rows = await session.execute(
        select(Attempt.created_at, Attempt.is_correct).where(Attempt.student_id == student_id, Attempt.created_at >= since)
    )
    per_day: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for at, ok in rows.all():
        day = at.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz).date().isoformat()
        per_day[day][0] += 1
        per_day[day][1] += int(ok)
    month = []
    for i in range(29, -1, -1):
        day = (today - timedelta(days=i)).isoformat()
        total, correct = per_day.get(day, [0, 0])
        month.append({"date": day, "answers": total, "correct": correct})

    neatness = await session.scalar(
        select(func.avg(WorkCheckItem.neatness)).where(
            WorkCheckItem.student_user_id == student_id, WorkCheckItem.confirmed_at.is_not(None), WorkCheckItem.neatness.is_not(None)
        )
    )
    last_test = await session.scalar(
        select(DailyTest).where(DailyTest.student_id == student_id, DailyTest.status == "finished").order_by(desc(DailyTest.date))
    )
    last = None
    if last_test is not None:
        s = evening.summary(last_test)
        weak = await session.get(CurriculumTopic, s["weak_topic_id"]) if s["weak_topic_id"] else None
        last = {**s, "date": last_test.date.isoformat(), "weak_topic": _name(weak, lang) if weak else None}

    user = await session.get(User, student_id)
    return {
        "student": {"id": student_id, "name": user.display_name if user else "", "grade": student.grade,
                    "streak": student.streak, "evening_time": student.evening_time},
        "lights": lights,
        "week": month[-7:],
        "month": month,
        "neatness": None if neatness is None else round(neatness),
        "readiness": await readiness_view(session, student_id, lang),
        "last_evening": last,
    }


async def assign(session: AsyncSession, viewer: User, student_id: int, topic_id: int, note: str | None) -> Assignment:
    """«Прислать ребёнку задание» по теме: ребёнок получит его в боте."""
    if viewer.role not in ("parent", "teacher") or viewer.id == student_id:
        raise ReportError("forbidden", 403)
    await ensure_can_view(session, viewer, student_id)
    if await session.get(CurriculumTopic, topic_id) is None:
        raise ReportError("topic_not_found", 404)
    item = Assignment(from_user_id=viewer.id, student_id=student_id, topic_id=topic_id, note=(note or "").strip()[:500] or None)
    session.add(item)
    await session.flush()
    await events_repo.enqueue(session, EVENT_ASSIGNMENT_NEW, {"assignment_id": item.id})
    await session.commit()
    return item


async def set_evening_time(session: AsyncSession, viewer: User, student_id: int, value: str) -> Student:
    """Время напоминания о вечернем тесте выбирает семья (или сам ученик)."""
    if viewer.role == "teacher":
        raise ReportError("forbidden", 403)
    student = await ensure_can_view(session, viewer, student_id)
    try:
        h, m = (int(x) for x in value.split(":"))
    except ValueError:
        raise ReportError("bad_time", 422) from None
    settings = get_settings()
    chosen = f"{h:02d}:{m:02d}"
    # С начала окна теста и не позже 20:00 — поздние уведомления мешают сну
    if not (0 <= m < 60 and settings.evening_start <= chosen <= settings.evening_time_latest):
        raise ReportError("bad_time", 422)
    student.evening_time = chosen
    await session.commit()
    return student
