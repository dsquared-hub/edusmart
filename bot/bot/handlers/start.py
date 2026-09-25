"""/start, /menu, выбор роли."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.db.models import ROLES, User
from app.db.session import SessionLocal
from app.repositories.users import get_user
from app.services.accounts import choose_role
from bot.handlers.common import send_home

router = Router()


@router.message(CommandStart())
@router.message(Command("menu"))
async def cmd_start(message: Message, state: FSMContext, user: User) -> None:
    await state.clear()
    await send_home(message, user)


@router.callback_query(F.data.startswith("role:"))
async def on_role_selected(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    role = callback.data.split(":", 1)[1]
    if role not in ROLES:
        await callback.answer()
        return
    async with SessionLocal() as session:
        db_user = await get_user(session, user.id)
        await choose_role(session, db_user, role)
    await callback.answer()
    await state.clear()
    await send_home(callback.message, db_user)
