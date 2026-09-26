"""Web Push для PWA — уведомления без Telegram (дети пользуются только сайтом).

События из очереди (events) доставляются независимо от бота: у события своя отметка
pushed_at. Получатели и тексты — те же, что в боте: родителю — итог темы и вечернего
теста, ребёнку — задание и оценка, учителю — «проверка готова». Нажатие на уведомление
открывает нужную страницу. Мёртвые подписки (браузер отписался — 404/410) удаляются.

Ключи VAPID: python scripts/gen_vapid.py → VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY в .env.
Без ключей Web Push выключен, события помечаются как обработанные (не копятся).
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.i18n import t
from app.core.timeutil import local_now, utcnow
from app.db.models import (
    Assignment, CurriculumTopic, DailyTest, Event, PushSubscription, Student, User, WorkCheck, WorkCheckItem,
)
from app.db.session import SessionLocal, is_postgres
from app.repositories.students import get_parents_of, get_teachers_of

log = logging.getLogger(__name__)


@dataclass
class Push:
    title: str
    body: str
    url: str
    tag: str | None = None  # одинаковый tag — новое уведомление заменяет старое


class PushSender(Protocol):
    async def send(self, sub: PushSubscription, message: Push) -> int: ...  # HTTP-статус


class VapidSender:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def send(self, sub: PushSubscription, message: Push) -> int:
        from pywebpush import WebPushException, webpush

        def _send() -> int:
            try:
                r = webpush(
                    subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
                    data=json.dumps(message.__dict__, ensure_ascii=False),
                    vapid_private_key=self.settings.vapid_private_key,
                    vapid_claims={"sub": self.settings.vapid_subject},
                    ttl=12 * 3600,
                    timeout=10,
                )
                return r.status_code
            except WebPushException as exc:
                return exc.response.status_code if exc.response is not None else 500

        return await asyncio.to_thread(_send)


class MemoryPushSender:
    """Тесты: запоминаем отправленное; endpoint с «gone» ведёт себя как отписавшийся браузер."""

    def __init__(self):
        self.sent: list[tuple[int, Push]] = []

    async def send(self, sub: PushSubscription, message: Push) -> int:
        if "gone" in sub.endpoint:
            return 410
        self.sent.append((sub.user_id, message))
        return 201


def push_enabled(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.vapid_public_key and settings.vapid_private_key)


def make_sender(settings: Settings | None = None) -> PushSender | None:
    settings = settings or get_settings()
    return VapidSender(settings) if push_enabled(settings) else None


# ---------- Подписки ----------

async def subscribe(session: AsyncSession, user: User, endpoint: str, p256dh: str, auth: str, user_agent: str | None) -> None:
    """Одно устройство (endpoint) — один пользователь: вошёл другой — подписка переходит к нему."""
    sub = await session.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    if sub is None:
        sub = PushSubscription(endpoint=endpoint, user_id=user.id, p256dh=p256dh, auth=auth)
        session.add(sub)
    sub.user_id, sub.p256dh, sub.auth = user.id, p256dh, auth
    sub.user_agent = (user_agent or "")[:255] or None
    await session.commit()


async def unsubscribe(session: AsyncSession, user: User, endpoint: str) -> None:
    await session.execute(delete(PushSubscription).where(PushSubscription.endpoint == endpoint, PushSubscription.user_id == user.id))
    await session.commit()


async def send_to(session: AsyncSession, sender: PushSender, user: User | None, message: Push) -> int:
    """Все устройства пользователя. Возвращает, на сколько устройств доставлено."""
    if user is None:
        return 0
    delivered = 0
    for sub in list(await session.scalars(select(PushSubscription).where(PushSubscription.user_id == user.id))):
        status = await sender.send(sub, message)
        if status in (404, 410):
            await session.delete(sub)  # браузер отписался или переустановлен
        elif 200 <= status < 300:
            sub.last_success_at = utcnow()
            delivered += 1
        else:
            log.warning("Web Push %s → %s", sub.id, status)
    return delivered


# ---------- События → уведомления ----------

def _lang(user: User) -> str:
    return user.lang if user.lang in ("ru", "uz", "en") else "ru"


def _child(user: User | None, lang: str) -> str:
    return (user.full_name if user and user.full_name else None) or t("default_child", lang)


async def _topic_completed(session, sender, p: dict) -> None:
    student = await session.get(User, p["student_user_id"])
    for parent in await get_parents_of(session, p["student_user_id"]):
        lang = _lang(parent)
        await send_to(session, sender, parent, Push(
            t("push_topic_done_title", lang, name=_child(student, lang)),
            t("push_topic_done_body", lang, title=p.get("title") or "", earned=p.get("points_earned", 0)),
            f"/family/{p['student_user_id']}",
        ))
    for teacher in await get_teachers_of(session, p["student_user_id"]):
        lang = _lang(teacher)
        await send_to(session, sender, teacher, Push(
            t("push_topic_done_title", lang, name=student.display_name if student else ""),
            t("push_topic_done_body", lang, title=p.get("title") or "", earned=p.get("points_earned", 0)),
            "/teacher",
        ))


async def _evening_done(session, sender, p: dict) -> None:
    from app.services.evening import summary

    test = await session.get(DailyTest, p["test_id"])
    if test is None:
        return
    s = summary(test)
    student = await session.get(User, test.student_id)
    weak = await session.get(CurriculumTopic, s["weak_topic_id"]) if s["weak_topic_id"] else None
    for parent in await get_parents_of(session, test.student_id):
        lang = _lang(parent)
        body = t("push_evening_weak", lang, topic=weak.name(lang)) if weak else t("push_evening_all", lang)
        await send_to(session, sender, parent, Push(
            t("push_evening_title", lang, name=_child(student, lang), n=s["topics_understood"], total=s["topics_total"]),
            body, f"/family/{test.student_id}", tag=f"evening-{test.student_id}",
        ))


async def _assignment(session, sender, p: dict) -> None:
    item = await session.get(Assignment, p["assignment_id"])
    if item is None:
        return
    student = await session.get(User, item.student_id)
    topic = await session.get(CurriculumTopic, item.topic_id)
    if student is None or topic is None:
        return
    lang = _lang(student)
    await send_to(session, sender, student, Push(
        t("push_assignment_title", lang), f"{topic.name(lang)}{' — ' + item.note if item.note else ''}", "/learn",
    ))


async def _work_graded(session, sender, p: dict) -> None:
    item = await session.get(WorkCheckItem, p["item_id"])
    if item is None or item.student_user_id is None or item.confirmed_at is None:
        return
    check = await session.get(WorkCheck, item.check_id)
    student = await session.get(User, item.student_user_id)
    for user, url in [(u, f"/family/{item.student_user_id}") for u in await get_parents_of(session, item.student_user_id)] + [(student, "/")]:
        if user is None:
            continue
        lang = _lang(user)
        await send_to(session, sender, user, Push(
            t("push_work_title", lang, title=check.title), t("push_work_body", lang, score=item.final_score, max=check.max_score), url,
        ))


async def _check_ready(session, sender, p: dict) -> None:
    check = await session.get(WorkCheck, p["check_id"])
    if check is None:
        return
    teacher = await session.get(User, check.teacher_user_id)
    if teacher is None:
        return
    lang = _lang(teacher)
    await send_to(session, sender, teacher, Push(
        t("push_check_title", lang, title=check.title), t("push_check_body", lang), f"/teacher/checks/{check.id}", tag=f"check-{check.id}",
    ))


async def _evening_missed(session, sender, p: dict) -> None:
    student = await session.get(User, p["student_user_id"])
    for parent in await get_parents_of(session, p["student_user_id"]):
        lang = _lang(parent)
        await send_to(session, sender, parent, Push(
            t("push_evening_missed_title", lang, name=_child(student, lang)),
            t("push_evening_missed_body", lang), f"/family/{p['student_user_id']}", tag=f"evening-{p['student_user_id']}",
        ))


HANDLERS = {
    "topic_completed": _topic_completed,
    "evening_done": _evening_done,
    "evening_missed": _evening_missed,
    "assignment_new": _assignment,
    "work_graded": _work_graded,
    "check_ready": _check_ready,
}


async def process_once(sender: PushSender | None, limit: int = 50) -> int:
    async with SessionLocal() as session:
        stmt = select(Event).where(Event.pushed_at.is_(None)).order_by(Event.id).limit(limit)
        if is_postgres(session):
            stmt = stmt.with_for_update(skip_locked=True)
        events = list(await session.scalars(stmt))
        for event in events:
            handler = HANDLERS.get(event.type)
            if handler is not None and sender is not None:
                try:
                    await handler(session, sender, event.payload or {})
                except Exception:
                    log.exception("Web Push для события %s", event.id)
            event.pushed_at = utcnow()
        await session.commit()
    return len(events)


async def evening_reminders(sender: PushSender | None, now: datetime | None = None, settings: Settings | None = None) -> int:
    """Напоминание о вечернем тесте на устройства ребёнка — во время, выбранное семьёй,
    не чаще раза в день и только если тест не пройден."""
    from app.services.accounts import consent_is_current
    from app.services.evening import reminders_allowed

    settings = settings or get_settings()
    now = now or local_now()
    if sender is None or not reminders_allowed(now, settings):
        return 0
    sent = 0
    async with SessionLocal() as session:
        done = select(DailyTest.student_id).where(DailyTest.date == now.date(), DailyTest.status == "finished")
        with_push = select(PushSubscription.user_id)
        students = list(await session.scalars(
            select(Student).where(
                Student.evening_time <= now.strftime("%H:%M"),
                (Student.last_reminded_on.is_(None)) | (Student.last_reminded_on < now.date()),
                Student.user_id.not_in(done),
                Student.user_id.in_(with_push),
            )
        ))
        for student in students:
            if not consent_is_current(student):
                continue
            student.last_reminded_on = now.date()
            user = await session.get(User, student.user_id)
            lang = _lang(user)
            if await send_to(session, sender, user, Push(t("push_evening_reminder_title", lang), t("push_evening_reminder_body", lang), "/evening", tag="evening")):
                sent += 1
        await session.commit()
    return sent


async def run_worker(sender: PushSender | None, idle_seconds: float = 3.0) -> None:
    log.info("Web Push: %s", "включён" if sender else "выключен (нет VAPID-ключей)")
    ticks = 0
    while True:
        try:
            await process_once(sender)
            if ticks % 100 == 0:  # ~раз в 5 минут
                from app.services.evening import enqueue_parent_reminders

                await evening_reminders(sender)
                await enqueue_parent_reminders()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Ошибка обработчика Web Push")
        ticks += 1
        await asyncio.sleep(idle_seconds)
