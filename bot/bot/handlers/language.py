"""Выбор языка: /language и кнопка «🌐 Язык». Язык общий для бота, сайта и объяснений."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.core.i18n import SUPPORTED_LANGS, set_current_lang, t
from app.db.models import User
from app.db.session import SessionLocal
from app.repositories.users import get_user
from bot.handlers.common import send_home
from bot.keyboards import language_keyboard

router = Router()


@router.message(Command("language"))
async def cmd_language(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(t("choose_language"), reply_markup=language_keyboard())


@router.callback_query(F.data == "lang:menu")
async def on_language_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.answer(t("choose_language"), reply_markup=language_keyboard())


@router.callback_query(F.data.startswith("lang:set:"))
async def on_language_set(callback: CallbackQuery, user: User) -> None:
    lang = callback.data.rsplit(":", 1)[1]
    if lang not in SUPPORTED_LANGS:
        await callback.answer()
        return
    async with SessionLocal() as session:
        db_user = await get_user(session, user.id)
        db_user.lang = lang
        await session.commit()
    set_current_lang(lang)  # ответ и меню — уже на новом языке
    await callback.answer(t("language_set"))
    await callback.message.answer(t("language_set"))
    await send_home(callback.message, db_user)
