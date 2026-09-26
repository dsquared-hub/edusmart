"""Дашборд родителя 🟢/🟡/🔴 и дневное уведомление родителю (16:30) с тревогой о пропусках."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.core.timeutil import local_now, utcnow
from app.db.models import ActivityDay, DailyTest, Event, Student
from app.db.session import SessionLocal
from app.repositories.users import get_by_telegram
from app.services import web_push
from app.services.parent_day import enqueue_parent_day, missed_streak, study_week, week_line
from test_api import KID_TG, login, make_student
from test_web_push import _subscribe

PARENT_TG = KID_TG + 1


async def _history(kid_id: int, *, joined_days_ago: int, active: list[int], tested: list[int]) -> None:
    """Ученик пришёл joined_days_ago дней назад; active/tested — сколько дней назад занимался / прошёл тест."""
    today = local_now().date()
    async with SessionLocal() as s:
        (await s.get(Student, kid_id)).created_at = utcnow() - timedelta(days=joined_days_ago)
        for ago in active:
            s.add(ActivityDay(user_id=kid_id, date=today - timedelta(days=ago)))
        for ago in tested:
            s.add(DailyTest(student_id=kid_id, date=today - timedelta(days=ago), status="finished", topic_ids=[], slots=[]))
        await s.commit()


async def test_study_week_states(db):
    kid_id = await make_student()
    # 5 дней назад пришёл; 4 — тест, 3 — только занимался, 2 и 1 — пропуски, сегодня — ещё ничего
    await _history(kid_id, joined_days_ago=5, active=[4, 3], tested=[4])
    today = local_now().date()
    async with SessionLocal() as s:
        week = (await study_week(s, [kid_id], today))[kid_id]
    assert [d["state"] for d in week] == ["none", "missed", "done", "partial", "missed", "missed", "today"]
    assert week[-1]["date"] == today.isoformat()
    assert missed_streak(week) == 2
    assert week_line(week) == "⚪🔴🟢🟡🔴🔴⏳"


async def test_parent_day_push_once_with_alert(client):
    kid_id = await make_student()
    await _history(kid_id, joined_days_ago=10, active=[], tested=[])
    now = local_now()
    assert await enqueue_parent_day(now.replace(hour=16, minute=25)) == 0  # ещё рано
    assert await enqueue_parent_day(now.replace(hour=21, minute=5)) == 0  # тихий час
    assert await enqueue_parent_day(now.replace(hour=16, minute=30)) == 1
    assert await enqueue_parent_day(now.replace(hour=16, minute=35)) == 0  # раз в день

    async with SessionLocal() as s:
        event = await s.scalar(select(Event).where(Event.type == "parent_day"))
        assert event.payload["missed_days"] == 6 and event.payload["week"].endswith("🔴🔴⏳")
        parent_id = (await get_by_telegram(s, PARENT_TG)).id
    await _subscribe(parent_id, "https://push.example.com/mom")
    sender = web_push.MemoryPushSender()
    assert await web_push.process_once(sender) == 1
    uid, msg = sender.sent[0]
    assert uid == parent_id and "не занимается 6 дн." in msg.title and msg.url == "/parent"


async def test_parent_day_skips_children_without_parent_or_consent(client):
    await make_student(consent=False)
    async with SessionLocal() as s:
        from app.repositories.users import upsert_telegram_user
        from app.services.accounts import choose_role

        lonely = await upsert_telegram_user(s, 9100, None, "Без родителя")
        await choose_role(s, lonely, "student")
    assert await enqueue_parent_day(local_now().replace(hour=17, minute=0)) == 0


async def test_parent_cabinet_has_week_and_readiness(client):
    kid_id = await make_student()
    await _history(kid_id, joined_days_ago=3, active=[1], tested=[])
    body = (await client.get("/api/cabinet", headers=await login(client, PARENT_TG))).json()
    [child] = body["children"]
    assert child["id"] == kid_id
    assert [d["state"] for d in child["week"]][-4:] == ["missed", "missed", "partial", "today"]
    assert child["readiness"] == []  # вечерних тестов ещё не было — ERS не посчитан
