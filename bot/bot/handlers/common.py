"""Общие помощники хендлеров."""
from __future__ import annotations

from datetime import date, timedelta
from html import escape

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from app.core.config import get_settings
from app.core.i18n import t
from app.db.models import User
from app.db.session import SessionLocal
from app.repositories.students import get_student
from app.repositories.topics import list_in_progress
from app.core.timeutil import local_now
from app.services.accounts import consent_is_current
from app.services.cabinet import ChildCard, ClassSummary, parent_cabinet, teacher_cabinet
from app.services.parent_day import week_line
from bot.keyboards import (
    app_url,
    parent_menu_keyboard,
    role_keyboard,
    student_menu_keyboard,
    teacher_menu_keyboard,
)


async def safe_edit(message: Message, text: str, reply_markup=None) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        await message.answer(text, reply_markup=reply_markup)


def error_text(code: str, explain=None) -> str:
    settings = explain.settings if explain is not None else get_settings()
    return t(code, limit=settings.daily_explain_limit)


def _last_active(day: date | None) -> str:
    if day is None:
        return t("cabinet_never")
    today = local_now().date()
    if day == today:
        return t("cabinet_today")
    if day == today - timedelta(days=1):
        return t("cabinet_yesterday")
    return day.strftime("%d.%m")


def _evening(card: ChildCard) -> str:
    if card.evening is None:
        return t("cabinet_evening_none")
    if card.evening.status == "finished":
        return t("cabinet_evening_done", score=card.evening.score, total=card.evening.total)
    return t("cabinet_evening_active")


def _accuracy(value: int | None) -> str:
    return "—" if value is None else f"{value}%"


def _parent_cabinet_text(user: User, cards: list[ChildCard]) -> str:
    """Кабинет родителя: по каждому ребёнку — успехи и вечерний тест сегодня."""
    head = t("cabinet_parent", name=escape(user.display_name))
    if not cards:
        return head + "\n\n" + t("cabinet_no_children")
    blocks = []
    for card in cards:
        s = card.summary
        blocks.append(
            t(
                "cabinet_child",
                name=escape(s.name),
                grade=t("cabinet_grade", grade=s.grade) if s.grade else "",
                points=s.points,
                streak=s.streak,
                week=s.topics_week,
                accuracy=_accuracy(s.accuracy),
                evening=_evening(card),
                last=_last_active(s.last_active_on),
            )
        )
        if card.week:
            blocks[-1] += "\n" + t("cabinet_week", week=week_line(card.week))
        scores = [f"{escape(name)} {score}%" for name, score in card.readiness if score is not None]
        if scores:
            blocks[-1] += "\n" + t("cabinet_readiness", items=", ".join(scores))
    return head + "\n\n" + "\n\n".join(blocks)


def _teacher_cabinet_text(user: User, summary: ClassSummary) -> str:
    """Кабинет учителя: класс целиком и работы, ждущие проверки."""
    head = t("cabinet_teacher", name=escape(user.display_name))
    if not summary.students:
        return head + "\n\n" + t("cabinet_no_students")
    text = t(
        "cabinet_class",
        students=summary.students,
        active=summary.active_today,
        week=summary.topics_week,
        accuracy=_accuracy(summary.accuracy),
        checks=summary.checks_to_review,
    )
    if summary.weak:
        items = ", ".join(f"{escape(title)} ({n})" for title, n in summary.weak)
        text += "\n" + t("cabinet_weak", items=items)
    return head + "\n\n" + text


async def home(user: User) -> tuple[str, object]:
    """(текст, клавиатура) главного меню для роли пользователя."""
    if user.role == "student" and get_settings().bot_student_lessons:
        text = t("student_home")
        async with SessionLocal() as session:
            student = await get_student(session, user.id)
            resume = await list_in_progress(session, user.id, limit=1)
        if student is not None and not consent_is_current(student):
            text += "\n\n" + t("student_home_consent_wait")
        return text, student_menu_keyboard(resume[0] if resume else None)
    if user.role == "parent":
        async with SessionLocal() as session:
            cards = await parent_cabinet(session, user)
        return _parent_cabinet_text(user, cards), parent_menu_keyboard()
    if user.role == "teacher":
        async with SessionLocal() as session:
            summary = await teacher_cabinet(session, user)
        return _teacher_cabinet_text(user, summary), teacher_menu_keyboard()
    # Не зарегистрирован (или старый «ученик» в боте): «Я родитель» / «Я учитель».
    # Дети учатся в приложении (PWA) по логину и коду от взрослого.
    return t("start_welcome", site=app_url()), role_keyboard()


async def send_home(message: Message, user: User) -> None:
    text, kb = await home(user)
    await message.answer(text, reply_markup=kb)
