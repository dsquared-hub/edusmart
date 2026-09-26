"""/start и /menu. Выбор роли и регистрация — в handlers/registration.py."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.db.models import User
from app.services.registration import ADULT_ROLES
from bot.handlers.common import home, safe_edit, send_home
from bot.handlers.registration import ask_phone

router = Router()


@router.message(CommandStart())
@router.message(Command("menu"))
async def cmd_start(message: Message, state: FSMContext, user: User, command: CommandObject) -> None:
    # Ссылки с сайта t.me/<бот>?start=parent / ?start=teacher — сразу к регистрации этой роли
    if command.args in ADULT_ROLES and user.role not in ADULT_ROLES:
        await ask_phone(message, state, command.args)
        return
    await state.clear()
    await send_home(message, user)


@router.callback_query(F.data == "cabinet:refresh")
async def on_cabinet_refresh(callback: CallbackQuery, user: User) -> None:
    """«🔄 Обновить» под кабинетом — свежая сводка в том же сообщении."""
    await callback.answer()
    text, kb = await home(user)
    await safe_edit(callback.message, text, reply_markup=kb)
