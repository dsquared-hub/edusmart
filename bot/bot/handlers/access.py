"""Вход на сайт без Telegram: родитель/учитель выдаёт ученику логин и код."""
from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.core.config import get_settings
from app.core.i18n import t
from app.db.models import User
from app.db.session import SessionLocal
from app.repositories.users import get_user
from app.services.accounts import AccountError, create_child_access, regenerate_code

router = Router()


class AccessStates(StatesGroup):
    waiting_name = State()


@router.callback_query(F.data == "access:new")
async def on_new_access(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    if user.role not in ("parent", "teacher"):
        await callback.answer(t("forbidden"), show_alert=True)
        return
    await state.set_state(AccessStates.waiting_name)
    await callback.answer()
    await callback.message.answer(
        t("ask_child_name" if user.role == "parent" else "ask_student_name")
    )


@router.message(AccessStates.waiting_name, F.text)
async def on_child_name(message: Message, state: FSMContext, user: User) -> None:
    async with SessionLocal() as session:
        issuer = await get_user(session, user.id)
        try:
            issued = await create_child_access(session, issuer, message.text)
        except AccountError as exc:
            await message.answer(t(exc.code))
            return
    await state.clear()
    key = "access_created_parent" if user.role == "parent" else "access_created_teacher"
    await message.answer(
        t(
            key,
            name=escape(issued.user.full_name),
            site=get_settings().web_url,
            login=issued.login,
            code=issued.code,
            family_code=issued.student.family_code,
        )
    )


@router.message(AccessStates.waiting_name)
async def on_child_name_wrong(message: Message) -> None:
    await message.answer(t("name_required"))


@router.callback_query(F.data.startswith("newcode:"))
async def on_new_code(callback: CallbackQuery, user: User) -> None:
    student_id = int(callback.data.split(":", 1)[1])
    async with SessionLocal() as session:
        issuer = await get_user(session, user.id)
        try:
            issued = await regenerate_code(session, issuer, student_id)
        except AccountError as exc:
            await callback.answer(t(exc.code), show_alert=True)
            return
    await callback.answer()
    await callback.message.answer(
        t("access_regenerated", name=escape(issued.user.display_name), login=issued.login, code=issued.code)
    )
