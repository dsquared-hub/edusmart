"""Stories ученика: генерация с проверкой ответов, EduCoin один раз, доступ только к своим."""
from __future__ import annotations

from sqlalchemy import select

from app.db.models import LessonMaterial, Student
from app.db.session import SessionLocal
from app.main import app
from app.repositories.students import link_teacher
from test_api import login, make_student
from test_journal import MOM_TG, TEACHER_TG, _user

QUESTIONS = {3: 0, 5: 1}  # слайд → верный вариант в демо-Stories (gemini_stub._STORIES)


async def _create(client, headers, title: str = "дроби") -> dict:
    r = await client.post("/api/stories", json={"title": title, "subject": "math", "grade": 5}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def test_student_story_flow_and_coins(client):
    kid_id = await make_student()
    headers = await login(client)
    story = await _create(client, headers)
    assert story["slides"] == 6 and story["status"] == "new" and story["from_teacher"] is None
    cards = story["cards"]
    assert all("correct" not in c for c in cards)  # ответы не отдаём заранее
    assert [i for i, c in enumerate(cards) if "question" in c] == list(QUESTIONS)
    assert all(len(c["text"].split()) <= 30 for c in cards)

    sid = story["id"]
    r = await client.post(f"/api/stories/{sid}/complete", headers=headers)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "story_unanswered"

    wrong = await client.post(f"/api/stories/{sid}/answer", json={"slide": 3, "option": 2}, headers=headers)
    assert wrong.json() == {"right": False, "correct": 0, "explanation": wrong.json()["explanation"]}
    # вторая попытка верна, но первая уже засчитана как ошибка
    assert (await client.post(f"/api/stories/{sid}/answer", json={"slide": 3, "option": 0}, headers=headers)).json()["right"]
    assert (await client.post(f"/api/stories/{sid}/answer", json={"slide": 5, "option": 1}, headers=headers)).json()["right"]
    bad = await client.post(f"/api/stories/{sid}/answer", json={"slide": 0, "option": 0}, headers=headers)
    assert bad.status_code == 422  # на карточке без вопроса отвечать нечего

    done = (await client.post(f"/api/stories/{sid}/complete", headers=headers)).json()
    assert done == {"coins": 3, "awarded": True, "first_try": 1, "questions": 2, "total_coins": 3}
    again = (await client.post(f"/api/stories/{sid}/complete", headers=headers)).json()
    assert again["awarded"] is False and again["total_coins"] == 3  # коины — один раз

    opened = (await client.get(f"/api/stories/{sid}", headers=headers)).json()
    assert opened["status"] == "done" and opened["cards"][3]["correct"] == 0  # после ответа — видно
    feed = (await client.get("/api/stories", headers=headers)).json()
    assert [s["id"] for s in feed["stories"]] == [sid] and feed["coins"] == 3
    async with SessionLocal() as s:
        student = await s.get(Student, kid_id)
        assert student.coins == 3 and student.streak == 1


async def test_story_answers_are_verified_and_limit_shared(client):
    await make_student()
    headers = await login(client)
    lesson = app.state.explain.lesson
    lesson.wrong_answers = 1  # первая генерация с ошибкой в ответе — её отбракуют и сделают заново
    story = await _create(client, headers)
    first = await client.post(f"/api/stories/{story['id']}/answer", json={"slide": 3, "option": 0}, headers=headers)
    assert first.json()["right"]  # ученику не попал неверный ответ «8/3»
    assert lesson.verify_calls >= 1

    progress = (await client.get("/api/progress", headers=headers)).json()
    assert progress["explanations_left_today"] == progress["daily_limit"] - 1  # общий лимит с «Объясни тему»

    lesson.fail_next = True
    r = await client.post("/api/stories", json={"title": "проценты"}, headers=headers)
    assert r.status_code == 502
    progress2 = (await client.get("/api/progress", headers=headers)).json()
    assert progress2["explanations_left_today"] == progress["explanations_left_today"]  # попытка вернулась


async def test_story_needs_consent_and_student(client):
    await make_student(consent=False)
    r = await client.post("/api/stories", json={"title": "дроби"}, headers=await login(client))
    assert r.status_code == 403 and r.json()["detail"]["code"] == "consent_required"
    parent = await login(client, MOM_TG)
    assert (await client.post("/api/stories", json={"title": "дроби"}, headers=parent)).status_code == 403
    assert (await client.get("/api/stories", headers=parent)).status_code == 403


async def test_foreign_story_is_hidden(client):
    await make_student()
    story = await _create(client, await login(client))
    await make_student(tg_id=6000)
    other = await login(client, 6000)
    sid = story["id"]
    assert (await client.get(f"/api/stories/{sid}", headers=other)).status_code == 404
    r = await client.post(f"/api/stories/{sid}/answer", json={"slide": 3, "option": 0}, headers=other)
    assert r.status_code == 404
    assert (await client.post(f"/api/stories/{sid}/complete", headers=other)).status_code == 404
    assert (await client.get("/api/stories", headers=other)).json()["stories"] == []


async def _material(teacher_id: int) -> int:
    async with SessionLocal() as s:
        material = LessonMaterial(
            teacher_user_id=teacher_id,
            topic="Дроби",
            lang="ru",
            content={
                "plan": {}, "test": {}, "answer_key": [],
                "stories": [
                    {"title": "Дробь", "text": "Часть целого.", "illustration": ""},
                    {"title": "Проверка", "text": "Пицца на 8 частей.", "illustration": "",
                     "question": "Съели 3 куска — какая часть?", "options": ["3/8", "8/3"], "correct": 0},
                ],
            },
            sources=[],
        )
        s.add(material)
        await s.commit()
        return material.id


async def test_teacher_sends_stories_to_linked_students(client):
    kid_id = await make_student()
    await make_student(tg_id=6000)  # не ученик этого учителя
    teacher_id = await _user(TEACHER_TG, "teacher", "Учитель")
    async with SessionLocal() as s:
        await link_teacher(s, teacher_id, kid_id)
        await s.commit()
    material_id = await _material(teacher_id)
    teacher = await login(client, TEACHER_TG)

    r = await client.post(f"/api/v1/teacher/materials/{material_id}/stories", headers=teacher)
    assert r.status_code == 200 and r.json() == {"sent": 1}
    assert (await client.post(f"/api/v1/teacher/materials/{material_id}/stories", headers=teacher)).json() == {"sent": 0}

    feed = (await client.get("/api/stories", headers=await login(client))).json()["stories"]
    assert len(feed) == 1 and feed[0]["from_teacher"] == "Учитель" and feed[0]["slides"] == 2
    assert (await client.get("/api/stories", headers=await login(client, 6000))).json()["stories"] == []

    # чужой учитель не может разослать чужие материалы
    await _user(4040, "teacher", "Другой")
    r = await client.post(f"/api/v1/teacher/materials/{material_id}/stories", headers=await login(client, 4040))
    assert r.status_code == 404
    async with SessionLocal() as s:
        assert await s.scalar(select(Student.coins).where(Student.user_id == kid_id)) == 0

