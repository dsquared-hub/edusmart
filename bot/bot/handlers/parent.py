"""Родитель: привязка ребёнка по коду, согласие на обработку данных."""
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
from app.repositories.students import is_linked_parent
from app.repositories.users import get_user
from app.services.accounts import (
    AccountError,
    confirm_consent_for_children,
    delete_student_data,
    link_by_family_code,
)
from bot.keyboards import (
    delete_confirm_keyboard,
    parent_menu_keyboard,
    policy_consent_keyboard,
)

router = Router()


class ParentStates(StatesGroup):
    waiting_code = State()


@router.callback_query(F.data == "parent:bind")
async def on_bind(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ParentStates.waiting_code)
    await callback.answer()
    await callback.message.answer(t("ask_parent_code"))


@router.message(ParentStates.waiting_code, F.text)
async def on_parent_code(message: Message, state: FSMContext, user: User) -> None:
    async with SessionLocal() as session:
        try:
            _, created = await link_by_family_code(session, user, message.text, "parent")
        except AccountError as exc:
            await message.answer(t(exc.code))
            return
    await state.clear()
    await message.answer(
        t("parent_link_ok" if created else "already_linked"),
        reply_markup=parent_menu_keyboard(),
    )


@router.callback_query(F.data == "parent:consent")
async def on_consent_info(callback: CallbackQuery) -> None:
    await callback.answer()
    text = t("consent_intro") + t("consent_intro_version", version=get_settings().policy_version)
    await callback.message.answer(text, reply_markup=policy_consent_keyboard())


@router.callback_query(F.data == "consent:confirm")
async def on_consent_confirm(callback: CallbackQuery, user: User) -> None:
    async with SessionLocal() as session:
        count = await confirm_consent_for_children(session, user)
    if not count:
        await callback.answer(t("consent_need_bind_first"), show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(t("consent_done"))


# ---------- Удаление данных ребёнка (право родителя) ----------

@router.callback_query(F.data.startswith("delchild:yes:"))
async def on_delete_yes(callback: CallbackQuery, user: User) -> None:
    student_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionLocal() as session:
        parent = await get_user(session, user.id)
        try:
            name = await delete_student_data(session, parent, student_id)
        except AccountError as exc:
            await callback.answer(t(exc.code), show_alert=True)
            return
    await callback.answer()
    await callback.message.edit_text(t("delete_done", name=escape(name)))


@router.callback_query(F.data == "delchild:no")
async def on_delete_no(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(t("delete_cancelled"))


@router.callback_query(F.data.startswith("delchild:"))
async def on_delete_ask(callback: CallbackQuery, user: User) -> None:
    student_id = int(callback.data.split(":", 1)[1])
    async with SessionLocal() as session:
        linked = await is_linked_parent(session, user.id, student_id)
        child = await get_user(session, student_id) if linked else None
    if child is None:
        await callback.answer(t("forbidden"), show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        t("delete_confirm", name=escape(child.display_name)),
        reply_markup=delete_confirm_keyboard(student_id),
    )