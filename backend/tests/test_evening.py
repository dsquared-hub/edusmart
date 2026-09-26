"""Модуль 4: вечерний тест, Exam Readiness Score, заморозки серии, отчёт родителю."""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.timeutil import local_now, utcnow
from app.db.models import (
    ActivityDay, Attempt, BankQuestion, CurriculumSubject, CurriculumTopic, DailyTest, Event, ReadinessScore,
    Student, TeacherLink, Topic,
)
from app.db.session import SessionLocal
from app.repositories.users import upsert_telegram_user
from app.services import evening, readiness
from app.services.accounts import choose_role
from app.services.curriculum import SAMPLE, load_curriculum, match_topic
from app.services.gamification import mark_active
from app.services.questions import StubQuestionGenerator, pick_question
from test_api import CORRECT, KID_TG, login, make_student

PARENT_TG = KID_TG + 1


@pytest.fixture
async def curriculum(db):
    async with SessionLocal() as s:
        await load_curriculum(s, json.loads(SAMPLE.read_text(encoding="utf-8")))


async def topic_id(name_ru: str) -> int:
    async with SessionLocal() as s:
        return await s.scalar(select(CurriculumTopic.id).where(CurriculumTopic.name_ru == name_ru))


async def seven_grader(consent: bool = True) -> int:
    kid_id = await make_student(consent=consent)
    async with SessionLocal() as s:
        (await s.get(Student, kid_id)).grade = 7
        await s.commit()
    return kid_id


@pytest.fixture
def evening_time(monkeypatch):
    """Вечер сегодняшнего дня по Ташкенту — окно теста открыто."""
    at = local_now().replace(hour=19, minute=0)
    monkeypatch.setattr(evening, "local_now", lambda: at)
    return at


async def test_match_topic(curriculum):
    async with SessionLocal() as s:
        assert await match_topic(s, "площадь трапеции", "math", 7) == await topic_id("Площадь трапеции")
        assert await match_topic(s, "trapetsiya yuzi", None, 7) == await topic_id("Площадь трапеции")  # по-узбекски
        assert await match_topic(s, "фотосинтез", "math", 7) is None


async def test_evening_flow(client, curriculum, evening_time):
    kid_id = await seven_grader()
    kid = await login(client)
    # Сегодня — объяснение по теме программы; 3 дня назад — другая тема (на повторение)
    r = await client.post("/api/explain", data={"title": "Площадь трапеции", "subject": "math", "grade": "7"}, headers=kid)
    assert r.status_code == 200
    async with SessionLocal() as s:
        assert (await s.get(Topic, r.json()["id"])).curriculum_topic_id == await topic_id("Площадь трапеции")
        s.add(Topic(student_user_id=kid_id, title="Линейные уравнения", steps=[], created_at=utcnow() - timedelta(days=3),
                    curriculum_topic_id=await topic_id("Линейные уравнения")))
        points_before = (await s.get(Student, kid_id)).points
        await s.commit()

    status = (await client.get("/api/v1/evening", headers=kid)).json()
    assert status["open"] and status["test"] is None
    r = await client.post("/api/v1/evening/start", headers=kid)
    assert r.status_code == 200, r.text
    test_id, q = r.json()["id"], r.json()["question"]
    assert q["total"] == 6 and q["slot"] == 0 and q["difficulty"] == 2  # 5 по сегодняшней теме + 1 повторение
    assert "correct" not in q  # правильный ответ клиенту не отдаём

    async def right(slot: int) -> int:
        async with SessionLocal() as s:
            test = await s.get(DailyTest, test_id)
            return (await s.get(BankQuestion, test.slots[slot]["question_id"])).correct

    # 1) верно → сложнее
    r = (await client.post(f"/api/v1/evening/{test_id}/answer", json={"slot": 0, "option": await right(0), "time_ms": 9000}, headers=kid)).json()
    assert r["correct"] and r["points"] == 10 and r["question"]["difficulty"] == 3
    # повторный ответ на тот же слот (двойной клик) не засчитывается
    stale = await client.post(f"/api/v1/evening/{test_id}/answer", json={"slot": 0, "option": 0}, headers=kid)
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "stale_slot"

    # 2) ошибка → объяснение и вторая попытка; исправил → монеты за исправление, сложность ниже
    wrong = (await right(1) + 1) % 3
    r = (await client.post(f"/api/v1/evening/{test_id}/answer", json={"slot": 1, "option": wrong, "time_ms": 12000}, headers=kid)).json()
    assert r["retry"] and not r["correct"] and r["explanation"] and "question" not in r
    r = (await client.post(f"/api/v1/evening/{test_id}/answer", json={"slot": 1, "option": await right(1)}, headers=kid)).json()
    assert r["correct"] and r["points"] == get_settings().points_correction and r["question"]["difficulty"] == 2

    # 3) до конца: ещё одна двойная ошибка (правильный ответ раскрываем), остальные верно
    r = (await client.post(f"/api/v1/evening/{test_id}/answer", json={"slot": 2, "option": (await right(2) + 1) % 3}, headers=kid)).json()
    r = (await client.post(f"/api/v1/evening/{test_id}/answer", json={"slot": 2, "option": (await right(2) + 1) % 3}, headers=kid)).json()
    assert not r["correct"] and r["correct_option"] is not None
    for slot in range(3, 6):
        r = (await client.post(f"/api/v1/evening/{test_id}/answer", json={"slot": slot, "option": await right(slot), "time_ms": 8000}, headers=kid)).json()
    assert r["finished"]
    assert r["summary"]["score"] == 4 and r["summary"]["total"] == 6 and r["summary"]["corrected"] == 1
    assert r["summary"]["topics_total"] == 2 and r["summary"]["weak_topic"] == "Площадь трапеции"

    async with SessionLocal() as s:
        student = await s.get(Student, kid_id)
        assert student.points - points_before == 4 * 10 + 5
        assert await s.scalar(select(func.count(Attempt.id)).where(Attempt.student_id == kid_id)) == 6  # только первые попытки
        assert await s.scalar(select(func.count(Attempt.id)).where(Attempt.is_review)) == 1
        assert await s.scalar(select(Event).where(Event.type == evening.EVENT_EVENING_DONE)) is not None
        ers = list(await s.scalars(select(ReadinessScore).where(ReadinessScore.student_id == kid_id)))
        assert ers and all(x.score is None for x in ers)  # 6 ответов < 20 — «недостаточно данных»

    again = await client.post("/api/v1/evening/start", headers=kid)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "evening_done"


async def test_evening_guards(client, curriculum, monkeypatch):
    await seven_grader(consent=False)
    kid = await login(client)
    monkeypatch.setattr(evening, "local_now", lambda: local_now().replace(hour=19))
    r = await client.post("/api/v1/evening/start", headers=kid)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "consent_required"

    await make_student(tg_id=6100)
    other = await login(client, 6100)
    r = await client.post("/api/v1/evening/start", headers=other)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "nothing_to_test"  # ещё ничего не изучал

    monkeypatch.setattr(evening, "local_now", lambda: local_now().replace(hour=10))
    r = await client.post("/api/v1/evening/start", headers=other)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "evening_closed"


async def test_question_bank_is_cached(curriculum):
    generator = StubQuestionGenerator()
    async with SessionLocal() as s:
        topic = await s.get(CurriculumTopic, await topic_id("Проценты"))
        first = await pick_question(s, generator, topic, 2, "ru", set())
        again = await pick_question(s, generator, topic, 2, "ru", set())
        assert first.id == again.id and generator.calls == 1  # второй ученик — без запроса к ИИ
        await pick_question(s, generator, topic, 2, "ru", {q.id for q in await s.scalars(select(BankQuestion))})
        assert generator.calls == 2  # все вопросы уже видел — догенерировали


async def test_ers_formula(curriculum):
    kid_id = await seven_grader()
    peer_id = await make_student(tg_id=6200)
    async with SessionLocal() as s:
        teacher = await upsert_telegram_user(s, 6300, None, "Учитель")
        await choose_role(s, teacher, "teacher")
        s.add_all([TeacherLink(teacher_user_id=teacher.id, student_user_id=kid_id),
                   TeacherLink(teacher_user_id=teacher.id, student_user_id=peer_id)])
        subject = await s.scalar(select(CurriculumSubject).where(CurriculumSubject.code == "physics", CurriculumSubject.grade == 7))
        topics = list(await s.scalars(select(CurriculumTopic).where(CurriculumTopic.subject_id == subject.id).order_by(CurriculumTopic.order)))
        # 6 тем физики: 3 освоены (5/5), 1 на 60%, 2 не начаты. 23 ответа.
        for t in topics[:3]:
            s.add_all([Attempt(student_id=kid_id, topic_id=t.id, is_correct=True, time_ms=20000) for _ in range(5)])
        s.add_all([Attempt(student_id=kid_id, topic_id=topics[3].id, is_correct=i < 3, time_ms=20000) for i in range(5)])
        # повторения: 2 из 3 верно
        s.add_all([Attempt(student_id=kid_id, topic_id=topics[0].id, is_correct=i < 2, time_ms=20000, is_review=True) for i in range(3)])
        # одноклассник решает вдвое быстрее → V = 0.5
        s.add_all([Attempt(student_id=peer_id, topic_id=topics[0].id, is_correct=True, time_ms=10000) for _ in range(3)])
        # 12 дней активности из 30
        today = local_now().date()
        s.add_all([ActivityDay(user_id=kid_id, date=today - timedelta(days=i)) for i in range(12)])
        await s.commit()

        row = await readiness.compute(s, kid_id, subject.id)
        m, sv, v, r = 3 / 6, 2 / 3, 0.5, 12 / 30
        assert row.components["attempts"] == 23
        assert row.components["M"] == round(m, 3) and row.components["V"] == 0.5 and row.components["R"] == 0.4
        # освоение считается по последним 5 ответам темы: у topics[0] последние — повторения (2/5 верно)
        assert row.score == round(100 * (0.5 * row.components["M"] + 0.25 * sv + 0.15 * v + 0.1 * r))
        # совет: сначала самая слабая из начатых тем, затем не начатые
        assert row.components["advice"][:1] in ([topics[0].id], [topics[3].id])
        assert set(row.components["advice"]) <= {t.id for t in topics}

        other = await s.scalar(select(CurriculumSubject).where(CurriculumSubject.code == "english"))
        assert (await readiness.compute(s, kid_id, other.id)).score is None  # нет данных


async def test_streak_freezes(db):
    kid_id = await make_student()
    monday = date(2026, 9, 21)
    async with SessionLocal() as s:
        student = await s.get(Student, kid_id)
        student.streak, student.last_active_on = 10, monday
        await mark_active(s, student, monday + timedelta(days=3), 2)  # пропустил 2 дня → 2 заморозки
        assert student.streak == 11 and student.freezes_used == 2
        await mark_active(s, student, monday + timedelta(days=5), 2)  # ещё пропуск — заморозок нет
        assert student.streak == 1
        await mark_active(s, student, monday + timedelta(days=8), 2)  # новая неделя — снова 2 заморозки
        assert student.streak == 2 and student.freezes_used == 2


async def test_parent_report_and_assignment(client, curriculum, evening_time):
    kid_id = await seven_grader()
    t_id = await topic_id("Площадь трапеции")
    async with SessionLocal() as s:
        s.add_all([Attempt(student_id=kid_id, topic_id=t_id, is_correct=i % 2 == 0, time_ms=5000) for i in range(5)])
        await s.commit()
    parent = await login(client, PARENT_TG)
    report = (await client.get(f"/api/v1/family/report?student_id={kid_id}", headers=parent)).json()
    assert report["lights"][0] == {"topic_id": t_id, "topic": "Площадь трапеции", "subject": "Математика (алгебра, геометрия)",
                                   "accuracy": 60, "light": "yellow"}
    assert len(report["week"]) == 7 and len(report["month"]) == 30 and report["month"][-1]["answers"] == 5

    # «Прислать ребёнку задание» по слабой теме → ребёнку в бот и в список заданий
    r = await client.post("/api/v1/assignments", json={"student_id": kid_id, "topic_id": t_id, "note": "Повтори формулу"}, headers=parent)
    assert r.status_code == 200
    kid = await login(client)
    assert (await client.get("/api/v1/assignments", headers=kid)).json()["assignments"][0]["topic"] == "Площадь трапеции"

    assert (await client.put("/api/v1/family/evening-time", json={"student_id": kid_id, "time": "19:30"}, headers=parent)).json() == {"evening_time": "19:30"}
    assert (await client.put("/api/v1/family/evening-time", json={"student_id": kid_id, "time": "23:30"}, headers=parent)).status_code == 422

    # Чужой родитель — как будто ребёнка нет
    await make_student(tg_id=7000)
    stranger = await login(client, 7001)
    assert (await client.get(f"/api/v1/family/report?student_id={kid_id}", headers=stranger)).status_code == 404
    assert (await client.post("/api/v1/assignments", json={"student_id": kid_id, "topic_id": t_id}, headers=stranger)).status_code == 404
    assert (await client.get(f"/api/v1/readiness?student_id={kid_id}", headers=stranger)).status_code == 404


async def test_assignment_closes_when_topic_is_learned(client, curriculum):
    """Задание открывает «Объясни тему» с этой темой и закрывается, когда тема пройдена."""
    kid_id = await seven_grader()
    t_id = await topic_id("Площадь трапеции")
    parent = await login(client, KID_TG + 1)
    r = await client.post("/api/v1/assignments", json={"student_id": kid_id, "topic_id": t_id}, headers=parent)
    assignment_id = r.json()["id"]
    kid = await login(client)
    assert len((await client.get("/api/v1/assignments", headers=kid)).json()["assignments"]) == 1

    # чужое задание не привязывает тему
    other = await make_student(tg_id=7100)
    foreign = await client.post("/api/v1/assignments", json={"student_id": other, "topic_id": t_id}, headers=await login(client, 7101))
    r = await client.post("/api/explain", data={"title": "что-то", "assignment_id": str(foreign.json()["id"])}, headers=kid)
    async with SessionLocal() as s:
        assert (await s.get(Topic, r.json()["id"])).curriculum_topic_id != t_id

    r = await client.post("/api/explain", data={"title": "Площадь трапеции", "assignment_id": str(assignment_id)}, headers=kid)
    tid = r.json()["id"]
    for step, option in enumerate(CORRECT):
        await client.post(f"/api/explain/{tid}/answer", json={"step": step, "option": option}, headers=kid)
    assert (await client.get("/api/v1/assignments", headers=kid)).json()["assignments"] == []
    other_list = (await client.get("/api/v1/assignments", headers=await login(client, 7100))).json()["assignments"]
    assert len(other_list) == 1  # чужое задание не тронуто
