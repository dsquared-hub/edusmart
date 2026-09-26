"""Дашборд родителя 🟢/🔴 и дневное уведомление родителю (Dev-Spec, блок 2).

Неделя ребёнка по дням:
    done    🟢 — прошёл вечерний тест;
    partial 🟡 — занимался (тема, Stories), но теста не было;
    missed  🔴 — пропустил день;
    today   ⏳ — сегодня, ещё ничего;
    none    ⚪ — ребёнка тогда ещё не было на платформе.

Дневное уведомление (PARENT_DAY_PUSH, по умолчанию 16:30 по Ташкенту, пусто — выключено):
родителю в бот и Web Push — «вечерний тест в 17:00, 2 минуты». Если ребёнок вчера
пропустил — отмечаем это, с 2 дней подряд — тревога. Раз в день на ребёнка, не
позже «тихого часа». Отметка ставится условным UPDATE: бот и API вызывают это
одновременно без дублей.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.timeutil import local_now
from app.db.models import ActivityDay, DailyTest, ParentLink, Student
from app.db.session import SessionLocal
from app.repositories import events as events_repo
from app.services.accounts import consent_is_current

EVENT_PARENT_DAY = "parent_day"
WEEK_DAYS = 7
STATE_EMOJI = {"done": "🟢", "partial": "🟡", "missed": "🔴", "today": "⏳", "none": "⚪"}


async def study_week(
    session: AsyncSession, student_ids: list[int], today: date, days: int = WEEK_DAYS
) -> dict[int, list[dict]]:
    """{ученик: [{"date", "state"}]} — от самого старого дня к сегодняшнему."""
    if not student_ids:
        return {}
    start = today - timedelta(days=days - 1)
    joined = {
        s.user_id: s.created_at.date() if s.created_at else start
        for s in await session.scalars(select(Student).where(Student.user_id.in_(student_ids)))
    }
    active = {
        (uid, d)
        for uid, d in (
            await session.execute(
                select(ActivityDay.user_id, ActivityDay.date).where(
                    ActivityDay.user_id.in_(student_ids), ActivityDay.date >= start, ActivityDay.date <= today
                )
            )
        ).all()
    }
    tested = {
        (uid, d)
        for uid, d in (
            await session.execute(
                select(DailyTest.student_id, DailyTest.date).where(
                    DailyTest.student_id.in_(student_ids),
                    DailyTest.status == "finished",
                    DailyTest.date >= start,
                    DailyTest.date <= today,
                )
            )
        ).all()
    }
    out: dict[int, list[dict]] = {}
    for uid in student_ids:
        week = []
        for i in range(days - 1, -1, -1):
            day = today - timedelta(days=i)
            if (uid, day) in tested:
                state = "done"
            elif (uid, day) in active:
                state = "partial"
            elif day < joined.get(uid, start):
                state = "none"
            elif day == today:
                state = "today"
            else:
                state = "missed"
            week.append({"date": day.isoformat(), "state": state})
        out[uid] = week
    return out


def missed_streak(week: list[dict]) -> int:
    """Сколько дней подряд пропущено до сегодняшнего (сегодня не считаем — день не кончился)."""
    streak = 0
    for day in reversed(week[:-1]):
        if day["state"] != "missed":
            break
        streak += 1
    return streak


def week_line(week: list[dict]) -> str:
    return "".join(STATE_EMOJI[d["state"]] for d in week)


def _due(now: datetime, settings: Settings) -> bool:
    hm = now.strftime("%H:%M")
    return bool(settings.parent_day_push) and settings.parent_day_push <= hm < settings.reminder_quiet_after


async def enqueue_parent_day(now: datetime | None = None, settings: Settings | None = None) -> int:
    """Раз в день после PARENT_DAY_PUSH ставит в очередь уведомление родителям каждого ребёнка."""
    settings = settings or get_settings()
    now = now or local_now()
    if not _due(now, settings):
        return 0
    today = now.date()
    queued = 0
    async with SessionLocal() as session:
        students = list(
            await session.scalars(
                select(Student).where(
                    or_(Student.parent_day_pushed_on.is_(None), Student.parent_day_pushed_on < today),
                    Student.user_id.in_(select(ParentLink.student_user_id)),
                )
            )
        )
        students = [s for s in students if consent_is_current(s)]
        weeks = await study_week(session, [s.user_id for s in students], today)
        for student in students:
            claimed = await session.execute(
                update(Student)
                .where(
                    Student.user_id == student.user_id,
                    or_(Student.parent_day_pushed_on.is_(None), Student.parent_day_pushed_on < today),
                )
                .values(parent_day_pushed_on=today)
                .execution_options(synchronize_session=False)
            )
            if claimed.rowcount == 1:
                week = weeks.get(student.user_id, [])
                await events_repo.enqueue(
                    session,
                    EVENT_PARENT_DAY,
                    {"student_user_id": student.user_id, "missed_days": missed_streak(week), "week": week_line(week)},
                )
                queued += 1
        await session.commit()
    return queued
