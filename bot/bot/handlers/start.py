"""/start и /menu. Выбор роли и регистрация — в handlers/registration.py."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.db.models import User
from bot.handlers.common import send_home

router = Router()


@router.message(CommandStart())
@router.message(Command("menu"))
async def cmd_start(message: Message, state: FSMContext, user: User) -> None:
    await state.clear()
    await send_home(message, user)
