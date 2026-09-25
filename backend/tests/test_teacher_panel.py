"""Панель учителя (Модуль 5, п. 4.3): тепловая карта, «кому нужна помощь», вопросы класса, задания."""
from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy import func, select

from app.core.timeutil import utcnow
from app.db.models import Assignment, Attempt, CurriculumTopic, Event, TeacherLink, Topic
from app.db.session import SessionLocal
from app.repositories.users import upsert_telegram_user
from app.services.accounts import choose_role
from app.services.curriculum import SAMPLE, load_curriculum
from test_api import login, make_student

TEACHER_TG = 9100


async def setup_class():
    a = await make_student()
    b = await make_student(tg_id=6100)
    outsider = await make_student(tg_id=6200)
    async with SessionLocal() as s:
        await load_curriculum(s, json.loads(SAMPLE.read_text(encoding="utf-8")))
        teacher = await upsert_telegram_user(s, TEACHER_TG, None, "Учитель")
        await choose_role(s, teacher, "teacher")
        s.add_all([TeacherLink(teacher_user_id=teacher.id, student_user_id=a), TeacherLink(teacher_user_id=teacher.id, student_user_id=b)])
        fractions = await s.scalar(select(CurriculumTopic.id).where(CurriculumTopic.name_ru == "Обыкновенные дроби"))
        percent = await s.scalar(select(CurriculumTopic.id).where(CurriculumTopic.name_ru == "Проценты"))
        now = utcnow()
        # a: неделю назад — всё верно, эта неделя — почти всё неверно (падение)
        s.add_all([Attempt(student_id=a, topic_id=fractions, is_correct=True, created_at=now - timedelta(days=10, minutes=i)) for i in range(5)])
        s.add_all([Attempt(student_id=a, topic_id=fractions, is_correct=i == 0, created_at=now - timedelta(days=1, minutes=i)) for i in range(5)])
        # b: стабильно хорошо
        s.add_all([Attempt(student_id=b, topic_id=percent, is_correct=i != 0, created_at=now - timedelta(days=d, minutes=i))
                   for d in (2, 9) for i in range(4)])
        # Вопросы к ИИ: оба спрашивали про дроби, a — ещё про проценты
        s.add_all([Topic(student_user_id=a, title="дроби", steps=[], curriculum_topic_id=fractions),
                   Topic(student_user_id=b, title="как складывать дроби", steps=[], curriculum_topic_id=fractions),
                   Topic(student_user_id=a, title="проценты", steps=[], curriculum_topic_id=percent)])
        await s.commit()
    return a, b, outsider, fractions, percent


async def test_panel(client):
    a, b, outsider, fractions, percent = await setup_class()
    teacher = await login(client, TEACHER_TG)
    panel = (await client.get("/api/v1/teacher/panel", headers=teacher)).json()

    assert sorted(s["id"] for s in panel["students"]) == sorted([a, b])  # чужой ученик не виден
    topics = {t["id"]: t["name"] for t in panel["heatmap"]["topics"]}
    assert topics == {fractions: "Обыкновенные дроби", percent: "Проценты"}
    # освоение — по последним 5 ответам: у a это 1 из 5
    assert panel["heatmap"]["cells"][str(a)] == {str(fractions): 20}
    assert panel["heatmap"]["cells"][str(b)] == {str(percent): 60}

    [help_] = panel["needs_help"]
    assert help_["student_id"] == a and help_["before"] == 100 and help_["after"] == 20 and help_["drop"] == 80

    assert panel["questions"][0] == {"topic_id": fractions, "name": "Обыкновенные дроби", "students": 2, "asked": 2}


async def test_assign_class_and_access(client):
    a, b, outsider, fractions, _ = await setup_class()
    teacher = await login(client, TEACHER_TG)

    r = await client.post("/api/v1/teacher/assignments", json={"topic_id": fractions, "note": "К пятнице"}, headers=teacher)
    assert r.json() == {"assigned": 2}  # всему классу
    r = await client.post("/api/v1/teacher/assignments", json={"topic_id": fractions, "student_ids": [a]}, headers=teacher)
    assert r.json() == {"assigned": 1}  # одному ученику
    async with SessionLocal() as s:
        assert await s.scalar(select(func.count(Assignment.id))) == 3
        assert await s.scalar(select(func.count(Event.id)).where(Event.type == "assignment_new")) == 3

    r = await client.post("/api/v1/teacher/assignments", json={"topic_id": fractions, "student_ids": [outsider]}, headers=teacher)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "student_not_linked"
    student = await login(client)
    assert (await client.get("/api/v1/teacher/panel", headers=student)).status_code == 403

    topics = (await client.get("/api/v1/curriculum/topics?grade=5", headers=teacher)).json()["topics"]
    assert "Обыкновенные дроби" in [t["name"] for t in topics] and all(t["grade"] == 5 for t in topics)
