"""Поддержка на сайте: родитель/учитель пишет вопрос и видит ответы."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import api_error, current_user, get_session
from app.db.models import SupportTicket, User
from app.services import support

router = APIRouter(prefix="/api", tags=["support"])

_STATUS = {
    "support_only_adults": 403,
    "support_need_text": 422,
    "support_too_long": 422,
    "support_limit": 429,
}


class SupportIn(BaseModel):
    text: str = Field(min_length=1, max_length=support.MAX_TEXT)


def _utc_iso(value: datetime | None) -> str | None:
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def _ticket(ticket: SupportTicket) -> dict:
    return {
        "id": ticket.id,
        "text": ticket.text,
        "status": ticket.status,
        "reply": ticket.reply,
        "created_at": _utc_iso(ticket.created_at),
        "answered_at": _utc_iso(ticket.answered_at),
    }


@router.get("/support")
async def list_support(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    if user.role not in support.ROLES:
        raise api_error(403, "support_only_adults")
    tickets = await support.user_tickets(session, user.id)
    return {"tickets": [_ticket(t) for t in tickets], "max_per_day": support.MAX_PER_DAY}


@router.post("/support")
async def create_support(
    body: SupportIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    try:
        ticket = await support.create_ticket(session, user, body.text, notify_owner=True)
    except support.SupportError as exc:
        raise api_error(_STATUS.get(exc.code, 400), exc.code)
    return _ticket(ticket)
