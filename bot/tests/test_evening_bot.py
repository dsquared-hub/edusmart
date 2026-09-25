"""Бот: напоминание о вечернем тесте, итог родителю, задание ребёнку (Модуль 4)."""
from __future__ import annotations

import json

from sqlalchemy import select

from app.core.timeutil import local_now
from app.db.models import CurriculumTopic, DailyTest, Student
from app.db.session import SessionLocal
from app.repositories.users import get_by_telegram
from app.services.curriculum import SAMPLE, load_curriculum
from app.services.family_report import assign
from bot.events_worker import process_events_once
from bot.scheduler import evening_reminders
from app.repositories import events as events_repo
from app.services.evening import EVENT_EVENING_DONE
from test_bot_flow import KID, MOM, _student_with_consent


async def _topic(name: str) -> int:
    async with SessionLocal() as s:
        return await s.scalar(select(CurriculumTopic.id).where(CurriculumTopic.name_ru == name))


async def test_reminder_once_and_not_after_test(h):
    kid_id = await _student_with_consent(h)
    evening = local_now().replace(hour=19, minute=5)

    assert await evening_reminders(h.bot, evening) == 1
    msg = h.api.last(KID)
    assert "Вечерний тест готов" in msg.text
    assert [b.web_app.url for b in h.buttons(msg) if b.web_app] == ["https://edu.example.com/evening"]
    assert await evening_reminders(h.bot, evening.replace(minute=40)) == 0  # не чаще раза в день

    # Время семьи ещё не наступило / окно закрыто — не беспокоим
    async with SessionLocal() as s:
        student = await s.get(Student, kid_id)
        student.last_reminded_on, student.evening_time = None, "20:30"
        await s.commit()
    assert await evening_reminders(h.bot, evening) == 0
    assert await evening_reminders(h.bot, evening.replace(hour=23)) == 0

    # Тест уже пройден — напоминание не нужно
    async with SessionLocal() as s:
        s.add(DailyTest(student_id=kid_id, date=evening.date(), status="finished", topic_ids=[], slots=[]))
        await s.commit()
    assert await evening_reminders(h.bot, evening.replace(hour=21)) == 0


async def test_parent_gets_result_and_child_gets_task(h):
    kid_id = await _student_with_consent(h)
    async with SessionLocal() as s:
        await load_curriculum(s, json.loads(SAMPLE.read_text(encoding="utf-8")))
    fractions, percent = await _topic("Обыкновенные дроби"), await _topic("Проценты")
    async with SessionLocal() as s:
        test = DailyTest(
            student_id=kid_id, date=local_now().date(), status="finished", topic_ids=[fractions, percent], score=3,
            slots=[{"topic_id": fractions, "review": False, "result": "wrong"},
                   {"topic_id": fractions, "review": False, "result": "missed"},
                   {"topic_id": percent, "review": False, "result": "correct"},
                   {"topic_id": percent, "review": False, "result": "correct"}],
        )
        s.add(test)
        await s.flush()
        await events_repo.enqueue(s, EVENT_EVENING_DONE, {"test_id": test.id})
        await s.commit()
    await process_events_once(h.bot)
    parent = h.api.last(MOM).text
    assert "понял(а) 1 из 2 тем" in parent and "Слабая тема: <b>Обыкновенные дроби</b>" in parent

    async with SessionLocal() as s:
        mom = await get_by_telegram(s, MOM)
        await assign(s, mom, kid_id, fractions, "Повтори с примерами")
    await process_events_once(h.bot)
    task = h.api.last(KID).text
    assert "Родитель прислал(а) тебе задание" in task and "Обыкновенные дроби" in task and "Повтори с примерами" in task
