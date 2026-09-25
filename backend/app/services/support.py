"""Поддержка: обращения родителей и учителей (сайт и бот), ответы владельца в боте.

С сайта обращение уходит владельцу через очередь событий (бот доставляет
карточку с кнопкой «Ответить»); ответ автор видит на сайте и в Telegram.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import utcnow
from app.db.models import SupportTicket, User
from app.repositories import events as events_repo

MAX_TEXT = 2000
MAX_PER_DAY = 5  # защита владельца от спама обращениями
ROLES = ("parent", "teacher")
EVENT_SUPPORT_NEW = "support_new"


class SupportError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


async def create_ticket(
    session: AsyncSession,
    user: User,
    text: str,
    *,
    has_photo: bool = False,
    notify_owner: bool = False,
) -> SupportTicket:
    """notify_owner — обращение с сайта: карточку владельцу доставит бот из очереди."""
    if user.role not in ROLES:
        raise SupportError("support_only_adults")
    text = text.strip()
    if not text:
        raise SupportError("support_need_text")
    if len(text) > MAX_TEXT:
        raise SupportError("support_too_long")
    today = await session.scalar(
        select(func.count(SupportTicket.id)).where(
            SupportTicket.user_id == user.id,
            SupportTicket.created_at >= utcnow() - timedelta(days=1),
        )
    )
    if (today or 0) >= MAX_PER_DAY:
        raise SupportError("support_limit")
    ticket = SupportTicket(user_id=user.id, text=text, has_photo=has_photo, status="open")
    session.add(ticket)
    await session.flush()
    if notify_owner:
        await events_repo.enqueue(session, EVENT_SUPPORT_NEW, {"ticket_id": ticket.id})
    await session.commit()
    return ticket


async def user_tickets(session: AsyncSession, user_id: int, limit: int = 20) -> list[SupportTicket]:
    rows = await session.scalars(
        select(SupportTicket)
        .where(SupportTicket.user_id == user_id)
        .order_by(desc(SupportTicket.created_at), desc(SupportTicket.id))
        .limit(limit)
    )
    return list(rows)


async def answer_ticket(session: AsyncSession, ticket_id: int, reply: str) -> SupportTicket:
    ticket = await session.get(SupportTicket, ticket_id)
    if ticket is None:
        raise SupportError("support_not_found")
    if ticket.status == "answered":
        raise SupportError("support_already_answered")
    reply = reply.strip()
    if not reply:
        raise SupportError("support_need_text")
    if len(reply) > MAX_TEXT:
        raise SupportError("support_too_long")
    ticket.status = "answered"
    ticket.reply = reply
    ticket.answered_at = utcnow()
    await session.commit()
    return ticket


async def open_tickets(session: AsyncSession, limit: int = 10) -> list[tuple[SupportTicket, User]]:
    rows = await session.execute(
        select(SupportTicket, User)
        .join(User, User.id == SupportTicket.user_id)
        .where(SupportTicket.status == "open")
        .order_by(desc(SupportTicket.created_at))
        .limit(limit)
    )
    return [(ticket, user) for ticket, user in rows.all()]
