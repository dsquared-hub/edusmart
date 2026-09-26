"""Вход в приложение без Telegram: новый код для ребёнка / ученика.

Сам ребёнок регистрируется в handlers/registration.py (кнопка «Зарегистрировать ребёнка»).
"""
from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.core.i18n import t
from app.db.models import User
from app.db.session import SessionLocal
from app.repositories.users import get_user
from app.services.accounts import AccountError, regenerate_code

router = Router()


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
