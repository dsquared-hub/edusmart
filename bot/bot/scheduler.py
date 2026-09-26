"""Фоновые задачи: еженедельный отчёт для родителей и мягкое напоминание.

Таймзона по умолчанию — Ташкент (UTC+5), настраивается в .env (TIMEZONE).
"""
from __future__ import annotations

import logging
from html import escape
from datetime import timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.core.config import get_settings
from app.core.i18n import set_current_lang, t
from app.core.timeutil import local_now
from app.db.models import DailyTest, ParentLink, PushSubscription, Student, User
from app.db.session import SessionLocal
from app.repositories.students import (
    activity_days_between,
    get_children,
    get_parents_of,
    topics_completed_since,
)
from app.repositories.users import get_user
from app.services.accounts import consent_is_current
from app.services.evening import enqueue_parent_reminders, reminders_allowed
from bot.keyboards import evening_keyboard

log = logging.getLogger(__name__)


def _praise(topics: int) -> str:
    if topics == 0:
        return t("weekly_praise_0")
    if topics <= 2:
        return t("weekly_praise_1")
    return t("weekly_praise_2")


async def _name(session, user_id: int) -> str:
    user = await get_user(session, user_id)
    return escape((user.full_name if user else None) or t("default_child"))


async def weekly_report(bot) -> None:
    """Воскресенье 19:00: сколько тем закрыто, дни активности, похвала."""
    now = local_now()
    week_ago_dt = (now - timedelta(days=7)).replace(tzinfo=None)
    week_ago_day = now.date() - timedelta(days=7)

    async with SessionLocal() as session:
        parents = await session.scalars(
            select(User).where(
                User.id.in_(select(ParentLink.parent_user_id).distinct()),
                User.telegram_id.is_not(None),
            )
        )
        for parent in list(parents):
            children = await get_children(session, parent.id)
            if not children:
                continue
            set_current_lang(parent.lang)  # отчёт — на языке родителя
            lines = [t("weekly_header")]
            for child in children:
                topics = await topics_completed_since(session, child.user_id, week_ago_dt)
                days = await activity_days_between(
                    session, child.user_id, week_ago_day, now.date()
                )
                lines.append(
                    t(
                        "weekly_student",
                        name=await _name(session, child.user_id),
                        topics=len(topics),
                        days=days,
                        praise=_praise(len(topics)),
                    )
                )
            try:
                await bot.send_message(parent.telegram_id, "\n".join(lines))
            except Exception as exc:
                log.warning("Отчёт родителю %s не отправлен: %s", parent.id, exc)


async def three_day_nudge(bot) -> None:
    """Ежедневно: если ученик не заходил 3+ дня — мягкое сообщение родителю."""
    today = local_now().date()
    async with SessionLocal() as session:
        students = list(await session.scalars(select(Student)))
        for student in students:
            if not consent_is_current(student) or student.last_active_on is None:
                continue
            if (today - student.last_active_on).days < 3:
                continue
            for parent in await get_parents_of(session, student.user_id):
                if parent.telegram_id is None:
                    continue
                set_current_lang(parent.lang)
                name = await _name(session, student.user_id)
                try:
                    await bot.send_message(parent.telegram_id, t("nudge_text", name=name))
                except Exception as exc:
                    log.warning("Напоминание родителю %s не отправлено: %s", parent.id, exc)


async def evening_reminders(bot, now=None) -> int:
    """Каждые 5 минут: напоминание о вечернем тесте в выбранное семьёй время —
    не больше одного в день и только если тест сегодня ещё не пройден. Мягко, без давления.

    Детям бот пишет только в старом режиме BOT_STUDENT_LESSONS=1: теперь ребёнку
    напоминает приложение (Web Push), а родителю — parent_reminders ниже."""
    now = now or local_now()
    settings = get_settings()
    if not settings.bot_student_lessons or not reminders_allowed(now, settings):
        return 0
    sent = 0
    async with SessionLocal() as session:
        done_today = select(DailyTest.student_id).where(DailyTest.date == now.date(), DailyTest.status == "finished")
        # Ребёнок с Web Push (PWA) получает напоминание на устройство — бот ему не пишет
        with_push = select(PushSubscription.user_id)
        students = list(
            await session.scalars(
                select(Student).where(
                    Student.evening_time <= now.strftime("%H:%M"),
                    (Student.last_reminded_on.is_(None)) | (Student.last_reminded_on < now.date()),
                    Student.user_id.not_in(done_today),
                    Student.user_id.not_in(with_push),
                )
            )
        )
        for student in students:
            user = await get_user(session, student.user_id)
            if user is None or user.telegram_id is None or not consent_is_current(student):
                continue
            student.last_reminded_on = now.date()  # даже при ошибке доставки — не повторяем весь вечер
            set_current_lang(user.lang)
            try:
                await bot.send_message(user.telegram_id, t("evening_reminder"), reply_markup=evening_keyboard())
                sent += 1
            except Exception as exc:
                log.warning("Напоминание о тесте %s не отправлено: %s", user.id, exc)
        await session.commit()
    return sent


async def parent_reminders(bot=None, now=None) -> int:
    """Каждые 5 минут: ставит в очередь мягкое напоминание родителям (через час после
    времени ребёнка, не позже 20:30). Доставят очередь бота и Web Push."""
    return await enqueue_parent_reminders(now)


def setup_scheduler(bot, timezone: str) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=timezone)
    scheduler.add_job(
        weekly_report,
        CronTrigger(day_of_week="sun", hour=19, minute=0),
        args=[bot],
        id="weekly_report",
    )
    scheduler.add_job(
        three_day_nudge, CronTrigger(hour=9, minute=0), args=[bot], id="three_day_nudge"
    )
    scheduler.add_job(
        evening_reminders, CronTrigger(minute="*/5"), args=[bot], id="evening_reminders"
    )
    scheduler.add_job(
        parent_reminders, CronTrigger(minute="*/5"), args=[bot], id="parent_reminders"
    )
    return scheduler
