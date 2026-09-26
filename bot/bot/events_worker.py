"""Очередь событий (таблица events): сайт и бот пишут, бот доставляет в Telegram."""
from __future__ import annotations

import asyncio
import logging
from html import escape

from app.core.config import get_settings
from app.core.i18n import set_current_lang, t
from app.db.models import (
    Assignment, ContentReport, CurriculumTopic, DailyTest, SupportTicket, WorkCheck, WorkCheckItem,
)
from app.db.session import SessionLocal
from app.repositories.events import fetch_pending, mark_processed
from app.repositories.students import get_parents_of, get_teachers_of
from app.repositories.topics import get_topic
from app.repositories.users import get_by_telegram, get_user
from app.services.explain import EVENT_CONTENT_REPORT, EVENT_TOPIC_COMPLETED
from app.services.evening import EVENT_EVENING_DONE, EVENT_EVENING_MISSED
from app.services.evening import summary as evening_summary
from app.services.family_report import EVENT_ASSIGNMENT_NEW
from app.services.parent_day import EVENT_PARENT_DAY
from app.services.support import EVENT_SUPPORT_NEW
from app.services.work_checks import EVENT_CHECK_READY, EVENT_WORK_GRADED, check_items, review_level
from bot.handlers.support import ticket_card
from bot.keyboards import check_keyboard, support_reply_keyboard
from bot.render import describe

log = logging.getLogger(__name__)


async def _notify_topic_completed(bot, session, payload: dict) -> None:
    student = await get_user(session, payload["student_user_id"])
    if student is None:
        return
    for parent in await get_parents_of(session, student.id):
        if parent.telegram_id is None:
            continue
        set_current_lang(parent.lang)  # каждому родителю — на его языке
        text = t(
            "parent_topic_done",
            name=escape(student.full_name or t("default_child")),
            title=escape(payload.get("title") or ""),
            earned=payload.get("points_earned", 0),
            where=t("where_site") if payload.get("source") == "web" else "",
        )
        try:
            await bot.send_message(parent.telegram_id, text)
        except Exception as exc:  # родитель заблокировал бота и т.п.
            log.warning("Уведомление родителю %s не отправлено: %s", parent.id, exc)

    topic = await get_topic(session, payload["topic_id"]) if payload.get("topic_id") else None
    for teacher in await get_teachers_of(session, student.id):
        if teacher.telegram_id is None:
            continue
        set_current_lang(teacher.lang)
        text = t(
            "teacher_topic_done",
            name=escape(student.display_name),
            title=escape(payload.get("title") or ""),
            steps=topic.total_steps if topic else "—",
            earned=payload.get("points_earned", 0),
            where=t("where_site") if payload.get("source") == "web" else "",
        )
        try:
            await bot.send_message(teacher.telegram_id, text)
        except Exception as exc:
            log.warning("Уведомление учителю %s не отправлено: %s", teacher.id, exc)


async def _notify_content_report(bot, session, payload: dict) -> None:
    """Новая жалоба «⚠️ Здесь ошибка» — владельцу бота и учителям ученика."""
    report = await session.get(ContentReport, payload["report_id"])
    topic = await get_topic(session, payload["topic_id"])
    if report is None or topic is None:
        return
    student = await get_user(session, topic.student_user_id)
    recipients: dict[int, str] = {}
    owner_id = get_settings().owner_id
    if owner_id:
        owner = await get_by_telegram(session, owner_id)
        recipients[owner_id] = owner.lang if owner else "ru"
    for teacher in await get_teachers_of(session, topic.student_user_id):
        if teacher.telegram_id:
            recipients[teacher.telegram_id] = teacher.lang
    for chat_id, lang in recipients.items():
        set_current_lang(lang)
        text = t(
            "report_notify",
            name=escape(student.display_name if student else "—"),
            **describe(report, topic),
        )
        try:
            await bot.send_message(chat_id, text)
        except Exception as exc:
            log.warning("Жалоба не доставлена %s: %s", chat_id, exc)


async def _notify_support_new(bot, session, payload: dict) -> None:
    """Обращение в поддержку с сайта — владельцу, с кнопкой «Ответить»."""
    owner_id = get_settings().owner_id
    ticket = await session.get(SupportTicket, payload["ticket_id"])
    author = await get_user(session, ticket.user_id) if ticket else None
    if not owner_id or ticket is None or author is None:
        return  # владелец не задан — обращение ждёт в /support
    owner = await get_by_telegram(session, owner_id)
    set_current_lang(owner.lang if owner else "ru")
    text = ticket_card(ticket, author) + t("support_from_site")
    try:
        await bot.send_message(owner_id, text, reply_markup=support_reply_keyboard(ticket.id))
    except Exception as exc:
        log.warning("Обращение #%s не доставлено владельцу: %s", ticket.id, exc)


async def _send(bot, user, text: str, reply_markup=None) -> None:
    if user is None or user.telegram_id is None:
        return
    try:
        await bot.send_message(user.telegram_id, text, reply_markup=reply_markup)
    except Exception as exc:
        log.warning("Сообщение %s не доставлено: %s", user.id, exc)


async def _notify_check_ready(bot, session, payload: dict) -> None:
    """ИИ проверил пакет работ — учителю: сколько готово к подтверждению, сколько вручную."""
    check = await session.get(WorkCheck, payload["check_id"])
    if check is None:
        return
    teacher = await get_user(session, check.teacher_user_id)
    items = await check_items(session, check.id)
    settings = get_settings()
    levels = [review_level(i, settings) for i in items]
    set_current_lang(teacher.lang if teacher else "ru")
    text = t(
        "check_ready",
        title=escape(check.title),
        total=len(items),
        one_click=levels.count("one_click"),
        review=levels.count("review"),
        manual=levels.count("manual"),
    )
    await _send(bot, teacher, text, check_keyboard(check.id))


async def _notify_work_graded(bot, session, payload: dict) -> None:
    """Учитель подтвердил оценку — родителям и самому ученику (журнал уже обновлён)."""
    item = await session.get(WorkCheckItem, payload["item_id"])
    if item is None or item.student_user_id is None or item.confirmed_at is None:
        return
    check = await session.get(WorkCheck, item.check_id)
    student = await get_user(session, item.student_user_id)
    comment = item.teacher_comment or item.ai_comment or ""
    for user, key in [(p, "work_graded_parent") for p in await get_parents_of(session, item.student_user_id)] + [
        (student, "work_graded_student")
    ]:
        if user is None:
            continue
        set_current_lang(user.lang)
        text = t(
            key,
            name=escape(student.full_name if student and student.full_name else t("default_child")),
            title=escape(check.title),
            score=item.final_score,
            max=check.max_score,
            comment=f"\n💬 {escape(comment)}" if comment else "",
        )
        await _send(bot, user, text)


async def _notify_evening_done(bot, session, payload: dict) -> None:
    """Вечерний тест пройден — родителям: сколько тем понял и какая слабая (ТЗ 2.3.1)."""
    test = await session.get(DailyTest, payload["test_id"])
    if test is None:
        return
    s = evening_summary(test)
    student = await get_user(session, test.student_id)
    weak = await session.get(CurriculumTopic, s["weak_topic_id"]) if s["weak_topic_id"] else None
    for parent in await get_parents_of(session, test.student_id):
        set_current_lang(parent.lang)
        name = escape(student.full_name if student and student.full_name else t("default_child"))
        key = "evening_done_parent" if weak else "evening_done_parent_all"
        text = t(key, name=name, understood=s["topics_understood"], total=s["topics_total"],
                 weak=escape(weak.name(parent.lang)) if weak else "")
        await _send(bot, parent, text)


async def _notify_evening_missed(bot, session, payload: dict) -> None:
    """К вечеру тест не пройден — одно мягкое напоминание родителям (не позже 20:30)."""
    student = await get_user(session, payload["student_user_id"])
    if student is None:
        return
    for parent in await get_parents_of(session, student.id):
        set_current_lang(parent.lang)
        name = escape(student.full_name or t("default_child"))
        await _send(bot, parent, t("evening_missed_parent", name=name))


def parent_day_key(missed_days: int) -> str:
    """Обычное напоминание, «вчера пропустил» или тревога — с 2 пропущенных дней подряд."""
    return "parent_day_alert" if missed_days >= 2 else "parent_day_missed" if missed_days == 1 else "parent_day"


async def _notify_parent_day(bot, session, payload: dict) -> None:
    """16:30: «вечерний тест в 17:00, 2 минуты» + неделя 🟢/🔴 и тревога о пропусках."""
    student = await get_user(session, payload["student_user_id"])
    if student is None:
        return
    missed = int(payload.get("missed_days", 0))
    for parent in await get_parents_of(session, student.id):
        set_current_lang(parent.lang)
        name = escape(student.full_name or t("default_child"))
        text = t(parent_day_key(missed), name=name, n=missed, start=get_settings().evening_start)
        if payload.get("week"):
            text += "\n" + t("parent_day_week", week=payload["week"])
        await _send(bot, parent, text)


async def _notify_assignment(bot, session, payload: dict) -> None:
    """«Прислать ребёнку задание» — ученику в бот."""
    item = await session.get(Assignment, payload["assignment_id"])
    if item is None:
        return
    student = await get_user(session, item.student_id)
    sender = await get_user(session, item.from_user_id)
    topic = await session.get(CurriculumTopic, item.topic_id)
    if student is None or topic is None:
        return
    set_current_lang(student.lang)
    who = t("from_teacher") if sender and sender.role == "teacher" else t("from_parent")
    note = f"\n💬 {escape(item.note)}" if item.note else ""
    await _send(bot, student, t("assignment_new", who=who, topic=escape(topic.name(student.lang)), note=note))


HANDLERS = {
    EVENT_TOPIC_COMPLETED: _notify_topic_completed,
    EVENT_CONTENT_REPORT: _notify_content_report,
    EVENT_SUPPORT_NEW: _notify_support_new,
    EVENT_CHECK_READY: _notify_check_ready,
    EVENT_WORK_GRADED: _notify_work_graded,
    EVENT_EVENING_DONE: _notify_evening_done,
    EVENT_EVENING_MISSED: _notify_evening_missed,
    EVENT_ASSIGNMENT_NEW: _notify_assignment,
    EVENT_PARENT_DAY: _notify_parent_day,
}


async def process_events_once(bot, limit: int = 50) -> int:
    async with SessionLocal() as session:
        events = await fetch_pending(session, limit)
        for event in events:
            handler = HANDLERS.get(event.type)
            if handler is not None:
                await handler(bot, session, event.payload or {})
            mark_processed(event)
        await session.commit()
    return len(events)


async def run_events_worker(bot, interval: float) -> None:
    while True:
        try:
            await process_events_once(bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Ошибка обработки очереди событий")
        await asyncio.sleep(interval)
