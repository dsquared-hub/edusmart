"""Общие помощники хендлеров."""
from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from app.core.config import get_settings
from app.core.i18n import t
from app.db.models import User
from app.db.session import SessionLocal
from app.repositories.students import get_student
from app.repositories.topics import list_in_progress
from app.services.accounts import consent_is_current
from bot.keyboards import (
    app_url,
    parent_menu_keyboard,
    role_keyboard,
    student_app_keyboard,
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


async def home(user: User) -> tuple[str, object]:
    """(текст, клавиатура) главного меню для роли пользователя."""
    if user.role == "student" and not get_settings().bot_student_lessons:
        # Дети учатся в приложении (PWA), бот — для взрослых
        return t("student_home_app", site=app_url()), student_app_keyboard()
    if user.role == "student":
        text = t("student_home")
        async with SessionLocal() as session:
            student = await get_student(session, user.id)
            resume = await list_in_progress(session, user.id, limit=1)
        if student is not None and not consent_is_current(student):
            text += "\n\n" + t("student_home_consent_wait")
        return text, student_menu_keyboard(resume[0] if resume else None)
    if user.role == "parent":
        return t("parent_home"), parent_menu_keyboard()
    if user.role == "teacher":
        return t("teacher_home"), teacher_menu_keyboard()
    text = t("start_welcome")
    if not get_settings().bot_student_lessons:
        text += "\n\n" + t("start_kid_hint", site=app_url())
    return text, role_keyboard()


async def send_home(message: Message, user: User) -> None:
    text, kb = await home(user)
    await message.answer(text, reply_markup=kb)
