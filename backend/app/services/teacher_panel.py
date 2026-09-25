"""Панель учителя (Модуль 5, п. 4.3).

- Тепловая карта класса: строки — ученики, столбцы — темы, цвет — освоение
  (последние 5 ответов по теме).
- «Кому нужна помощь»: у кого точность за последнюю неделю упала относительно
  предыдущей (падение результатов за 2 недели).
- Частые вопросы класса к ИИ: какие темы класс не понял (объяснения «Не понял тему»).
- Задания всему классу или отдельным ученикам.
Класс учителя — ученики, привязанные к нему (teacher_links).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import utcnow
from app.db.models import Assignment, Attempt, CurriculumSubject, CurriculumTopic, Student, TeacherLink, Topic, User
from app.repositories import events as events_repo
from app.services.family_report import EVENT_ASSIGNMENT_NEW

LAST_N = 5
HELP_DROP_POINTS = 15  # падение точности на 15+ п.п. — повод помочь
HELP_MIN_ANSWERS = 3


class PanelError(Exception):
    def __init__(self, code: str, status: int = 403):
        super().__init__(code)
        self.code = code
        self.status = status


def _name(obj, lang: str) -> str:
    return {"uz": obj.name_uz, "en": obj.name_en}.get(lang, obj.name_ru)


async def class_students(session: AsyncSession, teacher: User) -> list[tuple[Student, User]]:
    if teacher.role != "teacher":
        raise PanelError("not_teacher")
    rows = await session.execute(
        select(Student, User)
        .join(TeacherLink, TeacherLink.student_user_id == Student.user_id)
        .join(User, User.id == Student.user_id)
        .where(TeacherLink.teacher_user_id == teacher.id)
        .order_by(User.full_name)
    )
    return [(s, u) for s, u in rows.all()]


async def heatmap(session: AsyncSession, student_ids: list[int], lang: str, subject_id: int | None = None) -> dict:
    if not student_ids:
        return {"topics": [], "cells": {}}
    stmt = (
        select(Attempt.student_id, Attempt.topic_id, Attempt.is_correct)
        .where(Attempt.student_id.in_(student_ids))
        .order_by(desc(Attempt.created_at), desc(Attempt.id))
    )
    if subject_id:
        stmt = stmt.join(CurriculumTopic, CurriculumTopic.id == Attempt.topic_id).where(CurriculumTopic.subject_id == subject_id)
    recent: dict[tuple[int, int], list[bool]] = defaultdict(list)
    for student_id, topic_id, ok in (await session.execute(stmt)).all():
        if len(recent[(student_id, topic_id)]) < LAST_N:  # последние 5 ответов (строки уже новые → старые)
            recent[(student_id, topic_id)].append(ok)
    topic_ids = sorted({t for _, t in recent})
    topics = list(
        await session.execute(
            select(CurriculumTopic, CurriculumSubject)
            .join(CurriculumSubject, CurriculumSubject.id == CurriculumTopic.subject_id)
            .where(CurriculumTopic.id.in_(topic_ids))
            .order_by(CurriculumSubject.code, CurriculumTopic.order)
        )
    )
    cells: dict[str, dict[str, int]] = defaultdict(dict)
    for (student_id, topic_id), answers in recent.items():
        cells[str(student_id)][str(topic_id)] = round(100 * sum(answers) / len(answers))
    return {
        "topics": [{"id": t.id, "name": _name(t, lang), "subject": _name(s, lang)} for t, s in topics],
        "cells": cells,
    }


async def needs_help(session: AsyncSession, students: list[tuple[Student, User]]) -> list[dict]:
    now = utcnow()
    week, two_weeks = now - timedelta(days=7), now - timedelta(days=14)
    ids = [s.user_id for s, _ in students]
    if not ids:
        return []
    rows = await session.execute(
        select(Attempt.student_id, Attempt.is_correct, Attempt.created_at)
        .where(Attempt.student_id.in_(ids), Attempt.created_at >= two_weeks)
    )
    halves: dict[int, dict[str, list[bool]]] = defaultdict(lambda: {"before": [], "after": []})
    for student_id, ok, at in rows.all():
        halves[student_id]["after" if at >= week else "before"].append(ok)
    names = {s.user_id: u.display_name for s, u in students}
    out = []
    for student_id, h in halves.items():
        if len(h["before"]) < HELP_MIN_ANSWERS or len(h["after"]) < HELP_MIN_ANSWERS:
            continue
        before = round(100 * sum(h["before"]) / len(h["before"]))
        after = round(100 * sum(h["after"]) / len(h["after"]))
        if before - after >= HELP_DROP_POINTS:
            out.append({"student_id": student_id, "name": names[student_id], "before": before, "after": after, "drop": before - after})
    return sorted(out, key=lambda x: x["drop"], reverse=True)


async def class_questions(session: AsyncSession, student_ids: list[int], lang: str, days: int = 30) -> list[dict]:
    """Что класс спрашивал у ИИ: темы объяснений за 30 дней, по числу учеников."""
    if not student_ids:
        return []
    rows = await session.execute(
        select(Topic.student_user_id, Topic.title, Topic.curriculum_topic_id)
        .where(Topic.student_user_id.in_(student_ids), Topic.created_at >= utcnow() - timedelta(days=days))
    )
    groups: dict[str, dict] = {}
    for student_id, title, curriculum_id in rows.all():
        key = f"t{curriculum_id}" if curriculum_id else f"q{(title or '').strip().lower()[:60]}"
        g = groups.setdefault(key, {"topic_id": curriculum_id, "title": title, "students": set(), "asked": 0})
        g["students"].add(student_id)
        g["asked"] += 1
    curriculum = {
        t.id: t for t in await session.scalars(
            select(CurriculumTopic).where(CurriculumTopic.id.in_([g["topic_id"] for g in groups.values() if g["topic_id"]]))
        )
    }
    out = [
        {
            "topic_id": g["topic_id"],
            "name": _name(curriculum[g["topic_id"]], lang) if g["topic_id"] in curriculum else g["title"],
            "students": len(g["students"]),
            "asked": g["asked"],
        }
        for g in groups.values()
    ]
    return sorted(out, key=lambda x: (x["students"], x["asked"]), reverse=True)[:10]


async def panel(session: AsyncSession, teacher: User, subject_id: int | None = None) -> dict:
    lang = teacher.lang if teacher.lang in ("ru", "uz", "en") else "ru"
    students = await class_students(session, teacher)
    ids = [s.user_id for s, _ in students]
    return {
        "students": [{"id": s.user_id, "name": u.display_name, "grade": s.grade} for s, u in students],
        "heatmap": await heatmap(session, ids, lang, subject_id),
        "needs_help": await needs_help(session, students),
        "questions": await class_questions(session, ids, lang),
    }


async def assign_class(
    session: AsyncSession, teacher: User, topic_id: int, student_ids: list[int] | None, note: str | None
) -> int:
    """Задание по теме всему классу (student_ids не указан) или выбранным ученикам."""
    linked = {s.user_id for s, _ in await class_students(session, teacher)}
    targets = linked if not student_ids else set(student_ids)
    if not targets or not targets <= linked:
        raise PanelError("student_not_linked", 403 if targets else 409)
    if await session.get(CurriculumTopic, topic_id) is None:
        raise PanelError("topic_not_found", 404)
    for student_id in sorted(targets):
        item = Assignment(from_user_id=teacher.id, student_id=student_id, topic_id=topic_id, note=(note or "").strip()[:500] or None)
        session.add(item)
        await session.flush()
        await events_repo.enqueue(session, EVENT_ASSIGNMENT_NEW, {"assignment_id": item.id})
    await session.commit()
    return len(targets)
