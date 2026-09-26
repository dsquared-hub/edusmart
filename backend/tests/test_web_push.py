"""PWA: Web Push-подписки, доставка событий без Telegram, напоминание о вечернем тесте."""
from __future__ import annotations

import json

from sqlalchemy import func, select

from app.core.timeutil import local_now, utcnow
from app.db.models import (
    Assignment, CurriculumTopic, Event, PushSubscription, Student, WorkCheck, WorkCheckItem,
)
from app.db.session import SessionLocal
from app.repositories import events as events_repo
from app.services import web_push
from app.services.curriculum import SAMPLE, load_curriculum
from test_api import KID_TG, login, make_student

PARENT_TG = KID_TG + 1
SUB = {"endpoint": "https://push.example.com/abc", "keys": {"p256dh": "B" * 40, "auth": "a" * 16}}


async def test_subscribe_api(client):
    await make_student()
    kid = await login(client)
    assert (await client.get("/api/v1/push/key")).json() == {"public_key": None}  # ключей нет — пуши выключены

    r = await client.post("/api/v1/push/subscribe", json={**SUB, "endpoint": "http://evil.example.com"}, headers=kid)
    assert r.status_code == 422  # только HTTPS push-сервисы
    assert (await client.post("/api/v1/push/subscribe", json=SUB, headers=kid)).json() == {"ok": True}
    assert (await client.post("/api/v1/push/subscribe", json=SUB, headers=kid)).json() == {"ok": True}  # повтор не дублирует

    # На том же устройстве вошёл родитель — подписка переходит к нему
    parent = await login(client, PARENT_TG)
    await client.post("/api/v1/push/subscribe", json=SUB, headers=parent)
    async with SessionLocal() as s:
        subs = list(await s.scalars(select(PushSubscription)))
        assert len(subs) == 1 and subs[0].user_id != (await s.scalar(select(Student.user_id)))

    await client.post("/api/v1/push/unsubscribe", json={"endpoint": SUB["endpoint"]}, headers=parent)
    async with SessionLocal() as s:
        assert await s.scalar(select(func.count(PushSubscription.id))) == 0
    assert (await client.post("/api/v1/push/test", headers=parent)).status_code == 503


async def _subscribe(user_id: int, endpoint: str) -> None:
    async with SessionLocal() as s:
        s.add(PushSubscription(user_id=user_id, endpoint=endpoint, p256dh="k", auth="a"))
        await s.commit()


async def test_events_delivered_without_telegram(client):
    kid_id = await make_student()  # вместе с родителем (PARENT_TG)
    async with SessionLocal() as s:
        await load_curriculum(s, json.loads(SAMPLE.read_text(encoding="utf-8")))
        from app.repositories.users import get_by_telegram

        parent_id = (await get_by_telegram(s, PARENT_TG)).id
        topic = await s.scalar(select(CurriculumTopic).where(CurriculumTopic.name_ru == "Проценты"))
        check = WorkCheck(teacher_user_id=parent_id, title="Контрольная", max_score=5, status="confirmed")
        s.add(check)
        await s.flush()
        item = WorkCheckItem(check_id=check.id, student_user_id=kid_id, file_name="a.jpg", mime="image/jpeg", storage_key="x",
                             status="confirmed", attempts=1, ai_score=4, confirmed_at=utcnow())
        assignment = Assignment(from_user_id=parent_id, student_id=kid_id, topic_id=topic.id, note="К пятнице")
        s.add_all([item, assignment])
        await s.flush()
        await events_repo.enqueue(s, "topic_completed", {"student_user_id": kid_id, "title": "дроби", "points_earned": 30})
        await events_repo.enqueue(s, "assignment_new", {"assignment_id": assignment.id})
        await events_repo.enqueue(s, "work_graded", {"item_id": item.id})
        await s.commit()
    await _subscribe(parent_id, "https://push.example.com/mom-phone")
    await _subscribe(parent_id, "https://push.example.com/gone-old-laptop")  # браузер отписался
    await _subscribe(kid_id, "https://push.example.com/kid-tablet")

    sender = web_push.MemoryPushSender()
    assert await web_push.process_once(sender) == 3
    to_parent = [m for uid, m in sender.sent if uid == parent_id]
    to_kid = [m for uid, m in sender.sent if uid == kid_id]
    assert [m.url for m in to_parent] == [f"/family/{kid_id}", f"/family/{kid_id}"]
    assert "закрыл(а) тему" in to_parent[0].title and "дроби" in to_parent[0].body
    assert to_parent[1].body == "Оценка: 4 из 5"
    assert [m.title for m in to_kid] == ["📌 Новое задание", "📝 Работа «Контрольная» проверена"]
    assert to_kid[0].body == "Проценты — К пятнице" and "<" not in to_kid[0].title  # без HTML-разметки бота

    async with SessionLocal() as s:
        # мёртвая подписка удалена, события отмечены — повторно не шлём
        assert await s.scalar(select(func.count(PushSubscription.id))) == 2
        assert await s.scalar(select(func.count(Event.id)).where(Event.pushed_at.is_(None))) == 0
        assert await s.scalar(select(func.count(Event.id)).where(Event.processed_at.is_(None))) == 3  # бот доставит своё
    assert await web_push.process_once(sender) == 0

    # Пуши выключены (нет ключей) — события не копятся
    async with SessionLocal() as s:
        await events_repo.enqueue(s, "topic_completed", {"student_user_id": kid_id, "title": "x", "points_earned": 0})
        await s.commit()
    assert await web_push.process_once(None) == 1


async def test_evening_reminder_via_push(client):
    kid_id = await make_student()
    other_id = await make_student(tg_id=6100)  # без подписки — ему напомнит бот
    await _subscribe(kid_id, "https://push.example.com/kid")
    sender = web_push.MemoryPushSender()
    evening = local_now().replace(hour=19, minute=5)

    assert await web_push.evening_reminders(sender, evening) == 1
    assert sender.sent[0][0] == kid_id and sender.sent[0][1].url == "/evening"
    assert await web_push.evening_reminders(sender, evening.replace(minute=30)) == 0  # раз в день
    assert await web_push.evening_reminders(sender, evening.replace(hour=23)) == 0  # окно закрыто
    async with SessionLocal() as s:
        assert (await s.get(Student, other_id)).last_reminded_on is None
        (await s.get(Student, kid_id)).last_reminded_on = None
        await s.commit()
    assert await web_push.evening_reminders(sender, evening.replace(hour=21, minute=10)) == 0  # тихий час


async def test_parent_reminder_push_and_time_limits(client):
    from app.services.evening import enqueue_parent_reminders

    kid_id = await make_student()  # вместе с родителем (PARENT_TG), согласие дано
    parent = await login(client, PARENT_TG)
    # Позже 20:00 выбрать нельзя; 20:00 — можно
    for bad in ("20:30", "21:00", "16:59", "25:00", "abc"):
        r = await client.put("/api/v1/family/evening-time", json={"student_id": kid_id, "time": bad}, headers=parent)
        assert r.status_code == 422, bad
    r = await client.put("/api/v1/family/evening-time", json={"student_id": kid_id, "time": "18:30"}, headers=parent)
    assert r.json() == {"evening_time": "18:30"}

    today = local_now()
    assert await enqueue_parent_reminders(today.replace(hour=19, minute=25)) == 0  # 18:30 + час ещё не наступил
    assert await enqueue_parent_reminders(today.replace(hour=19, minute=30)) == 1
    assert await enqueue_parent_reminders(today.replace(hour=19, minute=35)) == 0  # раз в день

    async with SessionLocal() as s:
        from app.repositories.users import get_by_telegram

        parent_id = (await get_by_telegram(s, PARENT_TG)).id
    await _subscribe(parent_id, "https://push.example.com/mom")
    sender = web_push.MemoryPushSender()
    assert await web_push.process_once(sender) == 1
    uid, msg = sender.sent[0]
    assert uid == parent_id and "вечерний тест" in msg.title and msg.url == f"/family/{kid_id}"
