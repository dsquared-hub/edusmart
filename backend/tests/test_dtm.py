"""ДТМ-симулятор: формат 3×10 + 30 + 30, баллы 1.1 / 3.1 / 2.1 (макс. 189), таймер по серверу."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select

from app.core.timeutil import utcnow
from app.db.models import DtmQuestion, DtmTest, Student
from app.db.session import SessionLocal
from test_api import KID_TG, login, make_student


async def _grade(kid_id: int, grade: int | None) -> None:
    async with SessionLocal() as s:
        (await s.get(Student, kid_id)).grade = grade
        await s.commit()


async def _start(client, headers, spec1: str = "physics", spec2: str = "english"):
    return await client.post("/api/dtm", json={"spec1": spec1, "spec2": spec2}, headers=headers)


async def _correct(test_id: int) -> list[int]:
    async with SessionLocal() as s:
        test = await s.get(DtmTest, test_id)
        ids = [slot["question_id"] for slot in test.slots]
        right = {q.id: q.correct for q in await s.scalars(select(DtmQuestion).where(DtmQuestion.id.in_(ids)))}
        return [right[i] for i in ids]


async def test_dtm_variant_scoring(client):
    kid_id = await make_student()
    await _grade(kid_id, 11)
    headers = await login(client)
    overview = (await client.get("/api/dtm", headers=headers)).json()
    assert overview["subjects"]["max_score"] == 189 and overview["subjects"]["minutes"] == 180

    r = await _start(client, headers)
    assert r.status_code == 200, r.text
    test = r.json()
    qs = test["questions"]
    assert len(qs) == 90 and test["seconds_left"] > 179 * 60
    assert [q["block"] for q in qs[:30]] == ["mandatory:ona_tili"] * 10 + ["mandatory:math"] * 10 + ["mandatory:history_uz"] * 10
    assert {q["block"] for q in qs[30:60]} == {"spec1"} and {q["block"] for q in qs[60:]} == {"spec2"}
    assert all("correct" not in q for q in qs)  # ответы не отдаём до конца
    assert len({q["question"] for q in qs}) == 90  # без повторов в варианте

    right = await _correct(test["id"])
    # верно: 10 вопросов родного языка, 5 по физике (спец1), 10 по английскому (спец2); один ответ сняли
    plan = list(range(10)) + list(range(30, 35)) + list(range(60, 70))
    for n in plan + [20]:
        await client.put(f"/api/dtm/{test['id']}/answer", json={"slot": n, "option": right[n]}, headers=headers)
    await client.put(f"/api/dtm/{test['id']}/answer", json={"slot": 20, "option": None}, headers=headers)
    wrong = (right[21] + 1) % 3
    await client.put(f"/api/dtm/{test['id']}/answer", json={"slot": 21, "option": wrong}, headers=headers)

    done = (await client.post(f"/api/dtm/{test['id']}/finish", headers=headers)).json()
    assert done["status"] == "finished"
    assert done["results"]["mandatory:ona_tili"]["points"] == 11.0
    assert done["results"]["mandatory:math"]["correct"] == 0
    assert done["results"]["spec1"]["points"] == 15.5 and done["results"]["spec2"]["points"] == 21.0
    assert done["score"] == 47.5
    assert all("correct" in q for q in done["questions"])  # после — разбор с ответами
    r = await client.put(f"/api/dtm/{test['id']}/answer", json={"slot": 0, "option": 0}, headers=headers)
    assert r.status_code == 409


async def test_dtm_timer_and_one_active(client):
    kid_id = await make_student()
    await _grade(kid_id, 10)
    headers = await login(client)
    test = (await _start(client, headers)).json()
    r = await _start(client, headers, "math", "chemistry")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "dtm_active"

    async with SessionLocal() as s:
        (await s.get(DtmTest, test["id"])).deadline_at = utcnow() - timedelta(seconds=1)  # время вышло
        await s.commit()
    r = await client.put(f"/api/dtm/{test['id']}/answer", json={"slot": 0, "option": 0}, headers=headers)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "dtm_finished"
    assert (await client.get(f"/api/dtm/{test['id']}", headers=headers)).json()["status"] == "finished"

    second = (await _start(client, headers, "math", "chemistry")).json()
    first_ids = {q["question"] for q in test["questions"]}
    repeated = [q for q in second["questions"] if q["question"] in first_ids]
    assert not repeated  # пока банка хватает — новые вопросы
    async with SessionLocal() as s:
        assert await s.scalar(select(func.count(DtmQuestion.id))) >= 150  # банк общий и растёт


async def test_dtm_rules_and_access(client):
    kid_id = await make_student()
    headers = await login(client)
    await _grade(kid_id, 6)
    r = await _start(client, headers)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "dtm_grade"
    await _grade(kid_id, None)  # класс не указан — пускаем
    assert (await _start(client, headers, "physics", "physics")).status_code == 422
    assert (await _start(client, headers, "physics", "astrology")).status_code == 422
    test = (await _start(client, headers)).json()

    await make_student(tg_id=6000)
    other = await login(client, 6000)
    assert (await client.get(f"/api/dtm/{test['id']}", headers=other)).status_code == 404
    assert (await client.put(f"/api/dtm/{test['id']}/answer", json={"slot": 0, "option": 0}, headers=other)).status_code == 404
    assert (await client.post(f"/api/dtm/{test['id']}/finish", headers=other)).status_code == 404
    parent = await login(client, KID_TG + 1)
    assert (await client.get("/api/dtm", headers=parent)).status_code == 403


async def test_dtm_stops_on_ai_quota(client, monkeypatch):
    """Лимит ключа Gemini: не долбим API дальше, ученику — понятная ошибка, готовое сохранено."""
    from app.api.routers.family import get_question_generator
    from app.main import app
    from app.services.questions import QuotaExceeded, StubQuestionGenerator

    calls = {"n": 0}

    class Limited(StubQuestionGenerator):
        async def generate(self, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] > 2:
                raise QuotaExceeded("429 RESOURCE_EXHAUSTED")
            return await super().generate(*args, **kwargs)

    app.dependency_overrides[get_question_generator] = lambda: Limited()
    try:
        kid_id = await make_student()
        await _grade(kid_id, 11)
        r = await _start(client, await login(client))
        assert r.status_code == 503 and r.json()["detail"]["code"] == "ai_busy"
        assert calls["n"] == 3  # после отказа — ни одного лишнего запроса
        async with SessionLocal() as s:
            assert await s.scalar(select(func.count(DtmQuestion.id))) == 20  # две пачки сохранены
    finally:
        app.dependency_overrides.pop(get_question_generator, None)
