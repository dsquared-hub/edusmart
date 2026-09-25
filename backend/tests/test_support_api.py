"""Поддержка на сайте: родитель/учитель пишет вопрос, видит статус и ответ."""
from __future__ import annotations

from sqlalchemy import select

from app.db.models import Event
from app.db.session import SessionLocal
from app.repositories.users import upsert_telegram_user
from app.services import support
from app.services.accounts import choose_role
from test_api import KID_TG, login, make_student

PARENT_TG = KID_TG + 1  # родитель, которого создаёт make_student


async def test_parent_sends_question_and_sees_reply(client):
    await make_student()
    headers = await login(client, PARENT_TG)
    assert (await client.get("/api/support", headers=headers)).json()["tickets"] == []

    r = await client.post("/api/support", json={"text": "  Не вижу отчёт  "}, headers=headers)
    assert r.status_code == 200, r.text
    ticket = r.json()
    assert ticket["text"] == "Не вижу отчёт" and ticket["status"] == "open" and ticket["reply"] is None

    # владельцу — через очередь событий (бот доставит карточку)
    async with SessionLocal() as s:
        event = await s.scalar(select(Event).where(Event.type == support.EVENT_SUPPORT_NEW))
        assert event.payload == {"ticket_id": ticket["id"]}
        await support.answer_ticket(s, ticket["id"], "Отчёт приходит по воскресеньям")

    [seen] = (await client.get("/api/support", headers=headers)).json()["tickets"]
    assert seen["status"] == "answered" and seen["reply"] == "Отчёт приходит по воскресеньям"
    assert seen["answered_at"].endswith("+00:00")


async def test_teacher_allowed_student_forbidden(client):
    await make_student()
    r = await client.post("/api/support", json={"text": "вопрос"}, headers=await login(client))
    assert r.status_code == 403 and r.json()["detail"]["code"] == "support_only_adults"
    assert (await client.get("/api/support", headers=await login(client))).status_code == 403

    async with SessionLocal() as s:
        teacher = await upsert_telegram_user(s, 3131, None, "Учитель")
        await choose_role(s, teacher, "teacher")
        await s.commit()
    r = await client.post("/api/support", json={"text": "вопрос"}, headers=await login(client, 3131))
    assert r.status_code == 200


async def test_validation_and_daily_limit(client):
    await make_student()
    headers = await login(client, PARENT_TG)
    assert (await client.post("/api/support", json={"text": ""}, headers=headers)).status_code == 422
    r = await client.post("/api/support", json={"text": "   "}, headers=headers)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "support_need_text"
    assert (await client.post("/api/support", json={"text": "x" * 2001}, headers=headers)).status_code == 422

    for n in range(support.MAX_PER_DAY):
        assert (await client.post("/api/support", json={"text": f"q{n}"}, headers=headers)).status_code == 200
    r = await client.post("/api/support", json={"text": "ещё"}, headers=headers)
    assert r.status_code == 429 and r.json()["detail"]["code"] == "support_limit"
    # чужие обращения не видны
    tickets = (await client.get("/api/support", headers=headers)).json()["tickets"]
    assert len(tickets) == support.MAX_PER_DAY and tickets[0]["text"] == f"q{support.MAX_PER_DAY - 1}"
