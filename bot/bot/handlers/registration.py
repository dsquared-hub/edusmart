"""Регистрация в боте: отдельно родитель и учитель, дальше — ребёнок / ученик.

Взрослый: /start → «Я родитель» / «Я учитель» (или ссылка ?start=parent / ?start=teacher)
          → «📱 Отправить номер» → зарегистрирован, получает свой вход на сайт.
Родитель: сразу — имя ребёнка → профиль и логин с кодом для приложения EDU.
Учитель:  меню учителя (добавить учеников, класс, журнал).
"""
from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.core.config import get_settings
from app.core.i18n import t
from app.db.models import User
from app.db.session import SessionLocal
from app.repositories.users import get_user
from app.services.accounts import AccountError, choose_role, issue_own_access
from app.services.registration import ADULT_ROLES, clean_name, register_adult, register_child
from bot.handlers.common import send_home
from bot.keyboards import (
    app_url,
    child_done_keyboard,
    child_name_keyboard,
    register_phone_keyboard,
)

router = Router()

NOT_COMMAND = F.text & ~F.text.startswith("/")  # команды (/start, /class…) идут своим обработчикам


class RegStates(StatesGroup):
    phone = State()
    child_name = State()


# ---------- Взрослый ----------

async def ask_phone(message: Message, state: FSMContext, role: str) -> None:
    """Шаг регистрации родителя или учителя: роль запоминаем, записываем её вместе с номером."""
    await state.clear()
    await state.set_state(RegStates.phone)
    await state.update_data(role=role)
    await message.answer(t(f"reg_ask_phone_{role}"), reply_markup=register_phone_keyboard())


@router.callback_query(F.data.startswith("role:"))
async def on_role(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    role = callback.data.split(":", 1)[1]
    if role == "student" and not get_settings().bot_student_lessons:
        await callback.answer(t("role_student_moved"), show_alert=True)
        return
    if role not in (*ADULT_ROLES, "student"):
        await callback.answer()
        return
    await callback.answer()
    if user.role in ADULT_ROLES:  # уже зарегистрирован — кнопка из старого сообщения
        await state.clear()
        await send_home(callback.message, user)
        return
    if role == "student":  # режим BOT_STUDENT_LESSONS=1
        async with SessionLocal() as session:
            db_user = await get_user(session, user.id)
            await choose_role(session, db_user, role)
        await state.clear()
        await send_home(callback.message, db_user)
        return
    await ask_phone(callback.message, state, role)


async def _ask_child_name(message: Message, state: FSMContext, role: str) -> None:
    await state.set_state(RegStates.child_name)
    if role == "parent":
        text = t("reg_child_ask_name", version=get_settings().policy_version)
    else:
        text = t("reg_student_ask_name")
    await message.answer(text, reply_markup=child_name_keyboard(with_policy=role == "parent"))


@router.message(F.contact)
async def on_contact(message: Message, state: FSMContext, user: User) -> None:
    if message.contact.user_id != message.from_user.id:
        await message.answer(t("reg_phone_not_own"), reply_markup=register_phone_keyboard())
        return
    in_registration = await state.get_state() == RegStates.phone.state
    role = (await state.get_data()).get("role") if in_registration else None
    registering = user.role not in ADULT_ROLES
    if registering and role not in ADULT_ROLES:  # номер без выбранной роли — сначала «Кто вы?»
        await state.clear()
        await message.answer(t("reg_phone_then_role"), reply_markup=ReplyKeyboardRemove())
        await send_home(message, user)
        return
    async with SessionLocal() as session:
        try:
            adult = await register_adult(session, user, message.contact.phone_number, role or user.role)
        except AccountError as exc:
            await message.answer(t(exc.code), reply_markup=register_phone_keyboard())
            return
        if registering:
            login, code = await issue_own_access(session, adult)
    await state.clear()
    if not registering:  # уже зарегистрированный взрослый просто сменил номер
        await message.answer(t("reg_phone_saved"), reply_markup=ReplyKeyboardRemove())
        await send_home(message, adult)
        return
    # Убираем кнопку «Отправить номер» и даём свой вход на сайт (не путать со входом ребёнка)
    await message.answer(t(f"reg_done_{adult.role}", name=escape(adult.display_name)), reply_markup=ReplyKeyboardRemove())
    await message.answer(t(f"site_access_{adult.role}", site=app_url(), login=login, code=code))
    if adult.role == "parent":
        await _ask_child_name(message, state, adult.role)  # родитель — сразу регистрирует ребёнка
    else:
        await send_home(message, adult)


@router.message(RegStates.phone, NOT_COMMAND)
async def on_phone_text(message: Message) -> None:
    # Номер текстом не принимаем: его нельзя проверить без SMS
    await message.answer(t("reg_phone_not_own"), reply_markup=register_phone_keyboard())


# ---------- Ребёнок ----------

@router.callback_query(F.data.in_({"reg:child", "access:new"}))  # access:new — кнопка из старых сообщений
async def on_child_start(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    if user.role not in ADULT_ROLES:
        await callback.answer(t("forbidden"), show_alert=True)
        return
    await state.clear()
    await callback.answer()
    await _ask_child_name(callback.message, state, user.role)


@router.message(RegStates.child_name, NOT_COMMAND)
async def on_child_name(message: Message, state: FSMContext, user: User) -> None:
    try:
        name = clean_name(message.text)
    except AccountError as exc:
        await message.answer(t(exc.code))
        return
    async with SessionLocal() as session:
        try:
            issued = await register_child(session, user, name, None)
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


@router.message(RegStates.child_name, ~F.text)
async def on_child_name_wrong(message: Message) -> None:
    await message.answer(t("reg_bad_name"))


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


@router.callback_query(F.data.startswith("reg:"))
async def on_outdated(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    """Кнопки прежней регистрации (имя, класс, согласие) — просто показываем меню."""
    await on_menu(callback, state, user)
