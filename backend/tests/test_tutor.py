"""Сократовский тьютор: не выдаёт ответ, «решено» — только когда ученик назвал ответ сам."""
from __future__ import annotations

from app.db.models import Student
from app.db.session import SessionLocal
from app.main import app
from test_api import KID_TG, login, make_student


async def _start(client, headers, text: str = "3/8 + 2/8 = ?") -> dict:
    r = await client.post("/api/tutor", data={"text": text, "subject": "math", "grade": 5}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _say(client, headers, tid: int, text: str):
    return await client.post(f"/api/tutor/{tid}/message", json={"text": text}, headers=headers)


async def test_socratic_dialog_until_student_solves(client):
    kid_id = await make_student()
    headers = await login(client)
    dialog = await _start(client, headers)
    assert dialog["problem"] == "Сложи дроби: 3/8 + 2/8."
    assert [m["role"] for m in dialog["messages"]] == ["student", "tutor"]
    assert "5/8" not in dialog["messages"][-1]["text"]  # ответ не выдан

    r = (await _say(client, headers, dialog["id"], "знаменатель остаётся 8")).json()
    assert r["status"] == "active" and "числителями" in r["messages"][-1]["text"]
    r = (await _say(client, headers, dialog["id"], "получается 5/8")).json()
    assert r["status"] == "solved" and r["points"] == 20
    assert (await _say(client, headers, dialog["id"], "ещё")).status_code == 409  # диалог закрыт

    async with SessionLocal() as s:
        assert (await s.get(Student, kid_id)).points == 20  # очки — один раз
    listed = (await client.get("/api/tutor", headers=headers)).json()["dialogs"]
    assert [d["id"] for d in listed] == [dialog["id"]] and listed[0]["status"] == "solved"


async def test_leaked_answer_is_replaced(client):
    await make_student()
    headers = await login(client)
    lesson = app.state.explain.lesson
    lesson.tutor_leaks = 1  # первая реплика «выдаёт ответ» — проверка отбраковывает, берём следующую
    dialog = await _start(client, headers)
    assert "5/8" not in dialog["messages"][-1]["text"]

    lesson.tutor_leaks = 5  # модель упорно выдаёт ответ — ученику уходит безопасная подсказка
    r = (await _say(client, headers, dialog["id"], "не знаю")).json()
    assert "5/8" not in r["messages"][-1]["text"] and "по шагам" in r["messages"][-1]["text"]
    assert r["status"] == "active"


async def test_tutor_limits_and_access(client):
    await make_student()
    headers = await login(client)
    dialog = await _start(client, headers)
    progress = (await client.get("/api/progress", headers=headers)).json()
    assert progress["explanations_left_today"] == progress["daily_limit"] - 1  # общий лимит

    await make_student(tg_id=6000)
    other = await login(client, 6000)
    assert (await client.get(f"/api/tutor/{dialog['id']}", headers=other)).status_code == 404
    assert (await _say(client, other, dialog["id"], "5/8")).status_code == 404
    parent = await login(client, KID_TG + 1)
    assert (await client.post("/api/tutor", data={"text": "x"}, headers=parent)).status_code == 403

    for _ in range(14):  # всего реплик ученика — 15 (первая ушла при старте)
        assert (await _say(client, headers, dialog["id"], "не знаю")).status_code == 200
    r = await _say(client, headers, dialog["id"], "не знаю")
    assert r.status_code == 429 and r.json()["detail"]["code"] == "tutor_turns_limit"


async def test_tutor_needs_consent_and_refunds_on_error(client):
    await make_student(consent=False)
    r = await client.post("/api/tutor", data={"text": "x"}, headers=await login(client))
    assert r.status_code == 403 and r.json()["detail"]["code"] == "consent_required"

    await make_student(tg_id=6000)
    headers = await login(client, 6000)
    app.state.explain.lesson.fail_next = True
    assert (await client.post("/api/tutor", data={"text": "x"}, headers=headers)).status_code == 502
    progress = (await client.get("/api/progress", headers=headers)).json()
    assert progress["explanations_left_today"] == progress["daily_limit"]  # попытка вернулась
