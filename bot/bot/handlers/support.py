"""Поддержка: родитель/учитель пишет вопрос → владелец получает и отвечает кнопкой.

Обращения хранятся в БД (support_tickets), поэтому ответить можно и после
перезапуска бота. Для владельца /support — список открытых обращений.
"""
from __future__ import annotations

import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.core.i18n import set_current_lang, t
from app.db.models import SupportTicket, User
from app.db.session import SessionLocal
from app.repositories.users import get_user
from app.services import support
from bot.keyboards import support_cancel_keyboard, support_reply_keyboard
from bot.security import SecurityManager

log = logging.getLogger(__name__)
router = Router()


class SupportStates(StatesGroup):
    waiting_question = State()
    waiting_reply = State()  # владелец пишет ответ


def _is_owner(user: User, security: SecurityManager) -> bool:
    return security.owner_id is not None and user.telegram_id == security.owner_id


def _role_name(role: str | None) -> str:
    return t(f"role_{role}") if role in ("student", "parent", "teacher") else "—"


def ticket_card(ticket: SupportTicket, author: User) -> str:
    """Карточка обращения для владельца (из бота и с сайта — через очередь событий)."""
    username = f" · @{escape(author.username)}" if author.username else ""
    return t(
        "support_owner_new",
        id=ticket.id,
        name=escape(author.display_name),
        role=_role_name(author.role),
        tg_id=author.telegram_id or "—",
        username=username,
        text=escape(ticket.text),
    )


async def _show_open_tickets(message: Message) -> None:
    async with SessionLocal() as session:
        rows = await support.open_tickets(session)
    if not rows:
        await message.answer(t("support_open_empty"))
        return
    for ticket, author in reversed(rows):  # старые сверху — отвечаем по порядку
        await message.answer(ticket_card(ticket, author), reply_markup=support_reply_keyboard(ticket.id))


async def _start(message: Message, state: FSMContext, user: User, security: SecurityManager) -> None:
    if _is_owner(user, security):
        await _show_open_tickets(message)
        return
    if user.role not in support.ROLES:
        await message.answer(t("support_only_adults"))
        return
    if security.owner_id is None:
        await message.answer(t("support_unavailable"))
        return
    await state.set_state(SupportStates.waiting_question)
    await message.answer(t("support_ask"), reply_markup=support_cancel_keyboard())


@router.message(Command("support"))
async def cmd_support(message: Message, state: FSMContext, user: User, security: SecurityManager) -> None:
    await _start(message, state, user, security)


@router.callback_query(F.data == "support:new")
async def on_support(callback: CallbackQuery, state: FSMContext, user: User, security: SecurityManager) -> None:
    await callback.answer()
    await _start(callback.message, state, user, security)


@router.callback_query(F.data == "support:cancel")
async def on_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.answer(t("support_cancelled"))


@router.message(SupportStates.waiting_question)
async def on_question(message: Message, state: FSMContext, user: User, security: SecurityManager, bot: Bot) -> None:
    text = message.text or message.caption or ""
    if message.text and message.text.startswith("/"):
        await state.clear()  # команда вместо вопроса — выходим из режима поддержки
        await message.answer(t("support_cancelled"))
        return
    async with SessionLocal() as session:
        try:
            ticket = await support.create_ticket(session, user, text, has_photo=bool(message.photo))
        except support.SupportError as exc:
            await message.answer(t(exc.code, limit=support.MAX_PER_DAY))
            if exc.code == "support_limit":
                await state.clear()
            return
    await state.clear()
    await message.answer(t("support_sent", id=ticket.id))

    owner_id = security.owner_id
    try:
        await bot.send_message(owner_id, ticket_card(ticket, user), reply_markup=support_reply_keyboard(ticket.id))
        if message.photo:  # скриншот — копией, без пересылки имени отправителя
            await bot.copy_message(owner_id, message.chat.id, message.message_id)
    except Exception as exc:  # владелец не запускал бота и т.п.
        log.warning("Обращение #%s не доставлено владельцу: %s", ticket.id, exc)


@router.callback_query(F.data.startswith("sup:reply:"))
async def on_reply_pressed(callback: CallbackQuery, state: FSMContext, user: User, security: SecurityManager) -> None:
    if not _is_owner(user, security):
        await callback.answer(t("forbidden"), show_alert=True)
        return
    ticket_id = int(callback.data.rsplit(":", 1)[1])
    await state.set_state(SupportStates.waiting_reply)
    await state.update_data(ticket_id=ticket_id)
    await callback.answer()
    await callback.message.answer(t("support_owner_ask_reply", id=ticket_id), reply_markup=support_cancel_keyboard())


@router.message(SupportStates.waiting_reply, F.text)
async def on_reply(message: Message, state: FSMContext, user: User, security: SecurityManager, bot: Bot) -> None:
    if not _is_owner(user, security):
        await state.clear()
        return
    ticket_id = (await state.get_data()).get("ticket_id")
    async with SessionLocal() as session:
        try:
            ticket = await support.answer_ticket(session, ticket_id, message.text)
        except support.SupportError as exc:
            await message.answer(t(exc.code, id=ticket_id))
            if exc.code != "support_too_long":
                await state.clear()
            return
        author = await get_user(session, ticket.user_id)
    await state.clear()

    owner_lang = user.lang
    set_current_lang(author.lang if author else owner_lang)  # ответ — на языке автора
    text = t("support_reply", id=ticket.id, text=escape(ticket.reply))
    set_current_lang(owner_lang)
    if author is not None and author.telegram_id is None:
        # Вход на сайт по логину и коду: Telegram нет, ответ он увидит на сайте
        await message.answer(t("support_reply_site", id=ticket.id))
        return
    try:
        if author is None:
            raise LookupError("автор обращения удалён")
        await bot.send_message(author.telegram_id, text)
    except Exception as exc:
        log.warning("Ответ на обращение #%s не доставлен: %s", ticket.id, exc)
        await message.answer(t("support_reply_failed", id=ticket.id))
        return
    await message.answer(t("support_reply_sent", id=ticket.id))
