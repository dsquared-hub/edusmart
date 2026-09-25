"""Вход на сайт через бота: /start login_<токен> → выбрать число, показанное на сайте."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.core.i18n import t
from app.db.models import User
from app.db.session import SessionLocal
from app.services import bot_login
from bot.handlers.common import safe_edit, send_home
from bot.keyboards import web_login_keyboard

router = Router()


@router.message(CommandStart(deep_link=True, magic=F.args.startswith(bot_login.PAYLOAD_PREFIX)))
async def on_login_link(message: Message, command: CommandObject, state: FSMContext) -> None:
    await state.clear()
    token = command.args[len(bot_login.PAYLOAD_PREFIX):]
    async with SessionLocal() as session:
        request = await bot_login.find_pending(session, token)
        if request is None:
            await message.answer(t("weblogin_expired"))
            return
        choices = bot_login.choices_for(request)
    await message.answer(t("weblogin_confirm"), reply_markup=web_login_keyboard(request.id, choices))


@router.callback_query(F.data.startswith("wl:"))
async def on_login_answer(callback: CallbackQuery, user: User) -> None:
    _, request_id, choice = callback.data.split(":", 2)
    chosen = int(choice) if choice.isdigit() else None
    async with SessionLocal() as session:
        result = await bot_login.answer(session, int(request_id), user, chosen)
    await callback.answer()
    await safe_edit(callback.message, t(f"weblogin_{result}"))
    if result == "confirmed" and user.role is None:
        await send_home(callback.message, user)  # выбрать роль — без неё на сайте делать нечего
