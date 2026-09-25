"""Профиль: /profile и кнопки «Профиль»."""
from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.core.i18n import t
from app.db.models import User
from app.db.session import SessionLocal
from app.repositories.students import completed_count, get_children, get_student
from app.repositories.users import get_user
from app.services.gamification import level_for
from bot.keyboards import children_keyboard

router = Router()


async def _student_profile(user_id: int) -> str | None:
    async with SessionLocal() as session:
        student = await get_student(session, user_id)
        if student is None:
            return None
        return t(
            "profile_student",
            level=level_for(student.points),
            points=student.points,
            streak=student.streak,
            topics=await completed_count(session, user_id),
            code=student.family_code,
        )


async def _parent_profile(user_id: int) -> tuple[str, object]:
    async with SessionLocal() as session:
        children = await get_children(session, user_id)
        if not children:
            return t("profile_parent_empty"), None
        lines = [t("profile_parent_header")]
        with_login, all_children = [], []
        for child in children:
            child_user = await get_user(session, child.user_id)
            name = escape(child_user.full_name or t("default_child"))
            login = t("profile_login_suffix", login=child_user.login) if child_user.login else ""
            lines.append(
                t(
                    "profile_parent_line",
                    name=name,
                    points=child.points,
                    streak=child.streak,
                    code=child.family_code,
                    login=login,
                )
            )
            all_children.append((child_user.id, child_user.full_name or t("default_child")))
            if child_user.login:
                with_login.append((child_user.id, child_user.full_name or t("default_child")))
    return "\n".join(lines), children_keyboard(with_login, all_children)


async def _profile(user: User) -> tuple[str, object]:
    if user.role == "student":
        return await _student_profile(user.id) or t("not_student"), None
    if user.role == "parent":
        return await _parent_profile(user.id)
    if user.role == "teacher":
        return t("profile_teacher"), None
    return t("choose_role_first"), None


@router.message(Command("profile"))
async def cmd_profile(message: Message, user: User) -> None:
    text, kb = await _profile(user)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.in_({"student:profile", "parent:profile"}))
async def on_profile_callback(callback: CallbackQuery, user: User) -> None:
    text, kb = await _profile(user)
    await callback.answer()
    await callback.message.answer(text, reply_markup=kb)
