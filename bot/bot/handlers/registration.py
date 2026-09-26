"""Регистрация в боте: взрослый (родитель / учитель) и ребёнок, которого он регистрирует.

Взрослый: роль → имя → номер телефона (кнопкой Telegram, можно пропустить).
Ребёнок:  имя → класс → согласие родителя (для родителя) → логин и код в приложение EDU.
"""
from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.core.config import get_settings
from app.core.i18n import SUPPORTED_LANGS, t
from app.db.models import User
from app.db.session import SessionLocal
from app.repositories.users import get_user
from app.services.accounts import AccountError, choose_role
from app.services.registration import ADULT_ROLES, attach_phone, clean_name, register_child, set_name
from bot.handlers.common import send_home
from bot.keyboards import (
    after_registration_keyboard,
    app_url,
    cancel_keyboard,
    child_consent_keyboard,
    child_done_keyboard,
    grade_keyboard,
    keep_name_keyboard,
    share_phone_keyboard,
)

router = Router()

NOT_COMMAND = F.text & ~F.text.startswith("/")  # команды (/start, /class…) идут своим обработчикам


class RegStates(StatesGroup):
    name = State()
    phone = State()
    child_name = State()
    child_grade = State()
    child_consent = State()


# ---------- Взрослый ----------

@router.callback_query(F.data.startswith("role:"))
async def on_role(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    role = callback.data.split(":", 1)[1]
    if role == "student" and not get_settings().bot_student_lessons:
        await callback.answer(t("role_student_moved"), show_alert=True)
        return
    if role not in (*ADULT_ROLES, "student"):
        await callback.answer()
        return
    async with SessionLocal() as session:
        db_user = await get_user(session, user.id)
        await choose_role(session, db_user, role)
    await callback.answer()
    await state.clear()
    if role == "student":  # старый режим BOT_STUDENT_LESSONS=1
        await send_home(callback.message, db_user)
        return
    await state.set_state(RegStates.name)
    await callback.message.answer(t("reg_ask_name"), reply_markup=keep_name_keyboard(callback.from_user.full_name))


async def _save_name(message: Message, state: FSMContext, user: User, name: str) -> None:
    async with SessionLocal() as session:
        try:
            await set_name(session, user, name)
        except AccountError as exc:
            await message.answer(t(exc.code))
            return
    await state.set_state(RegStates.phone)
    await message.answer(t("reg_ask_phone"), reply_markup=share_phone_keyboard())


@router.callback_query(RegStates.name, F.data == "reg:keepname")
async def on_keep_name(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    await callback.answer()
    await _save_name(callback.message, state, user, callback.from_user.full_name)


@router.message(RegStates.name, NOT_COMMAND)
async def on_name(message: Message, state: FSMContext, user: User) -> None:
    await _save_name(message, state, user, message.text)


def _is_skip(text: str | None) -> bool:
    return bool(text) and text.strip() in {t("btn_reg_skip", lang) for lang in SUPPORTED_LANGS}


async def _finish_adult(message: Message, state: FSMContext, user: User) -> None:
    await state.clear()
    async with SessionLocal() as session:
        db_user = await get_user(session, user.id)
    key = "reg_done_parent" if db_user.role == "parent" else "reg_done_teacher"
    # Сначала убираем кнопку «Поделиться номером», потом — меню с действиями
    await message.answer(t(key, name=escape(db_user.display_name)), reply_markup=ReplyKeyboardRemove())
    next_key = "reg_next_parent" if db_user.role == "parent" else "reg_next_teacher"
    await message.answer(t(next_key), reply_markup=after_registration_keyboard(db_user.role))


@router.message(RegStates.phone, F.contact)
async def on_contact(message: Message, state: FSMContext, user: User) -> None:
    if message.contact.user_id != message.from_user.id:
        await message.answer(t("reg_phone_not_own"), reply_markup=share_phone_keyboard())
        return
    async with SessionLocal() as session:
        try:
            await attach_phone(session, user, message.contact.phone_number)
        except AccountError as exc:
            await message.answer(t(exc.code), reply_markup=share_phone_keyboard())
            return
    await _finish_adult(message, state, user)


@router.message(RegStates.phone, NOT_COMMAND)
async def on_phone_text(message: Message, state: FSMContext, user: User) -> None:
    if _is_skip(message.text):
        await _finish_adult(message, state, user)
        return
    # Номер текстом не принимаем: его нельзя проверить без SMS
    await message.answer(t("reg_phone_not_own"), reply_markup=share_phone_keyboard())


# ---------- Ребёнок ----------

@router.callback_query(F.data.in_({"reg:child", "access:new"}))  # access:new — кнопка из старых сообщений
async def on_child_start(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    if user.role not in ADULT_ROLES:
        await callback.answer(t("forbidden"), show_alert=True)
        return
    await state.clear()
    await state.set_state(RegStates.child_name)
    await callback.answer()
    key = "reg_child_ask_name" if user.role == "parent" else "reg_student_ask_name"
    await callback.message.answer(t(key), reply_markup=cancel_keyboard())


@router.message(RegStates.child_name, NOT_COMMAND)
async def on_child_name(message: Message, state: FSMContext) -> None:
    try:
        name = clean_name(message.text)
    except AccountError as exc:
        await message.answer(t(exc.code))
        return
    await state.update_data(child_name=name)
    await state.set_state(RegStates.child_grade)
    await message.answer(t("reg_ask_grade", name=escape(name)), reply_markup=grade_keyboard())


@router.message(RegStates.child_name, ~F.text)
async def on_child_name_wrong(message: Message) -> None:
    await message.answer(t("reg_bad_name"))


@router.message(RegStates.child_grade, ~F.text | NOT_COMMAND)
async def on_grade_text(message: Message) -> None:
    await message.answer(t("reg_bad_grade"), reply_markup=grade_keyboard())


@router.callback_query(RegStates.child_grade, F.data.startswith("reg:grade:"))
async def on_grade(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    try:
        grade = int(callback.data.rsplit(":", 1)[1]) or None
    except ValueError:
        await callback.answer()
        return
    await state.update_data(grade=grade)
    await callback.answer()
    name = (await state.get_data()).get("child_name", "")
    if user.role == "parent":
        # Регистрируя ребёнка, родитель даёт согласие — явно, отдельной кнопкой
        await state.set_state(RegStates.child_consent)
        await callback.message.answer(
            t("reg_consent", name=escape(name), version=get_settings().policy_version),
            reply_markup=child_consent_keyboard(),
        )
        return
    await _create_child(callback.message, state, user)


@router.callback_query(RegStates.child_consent, F.data == "reg:consent")
async def on_child_consent(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    await callback.answer()
    await _create_child(callback.message, state, user)


async def _create_child(message: Message, state: FSMContext, user: User) -> None:
    data = await state.get_data()
    if not data.get("child_name"):  # кнопка из старого сообщения — начнём заново
        await state.clear()
        await message.answer(t("reg_cancelled"))
        return
    async with SessionLocal() as session:
        try:
            issued = await register_child(session, user, data["child_name"], data.get("grade"))
        except AccountError as exc:
            await state.clear()
            await message.answer(t(exc.code))
            return
    await state.clear()
    key = "reg_child_done" if user.role == "parent" else "reg_student_done"
    await message.answer(
        t(
            key,
            name=escape(issued.user.full_name),
            site=app_url(),
            login=issued.login,
            code=issued.code,
            family_code=issued.student.family_code,
        ),
        reply_markup=child_done_keyboard(user.role),
    )


@router.callback_query(F.data == "reg:cancel")
async def on_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.answer(t("reg_cancelled"))


@router.callback_query(F.data == "reg:menu")
async def on_menu(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    await state.clear()
    await callback.answer()
    async with SessionLocal() as session:
        db_user = await get_user(session, user.id)
    await send_home(callback.message, db_user)
