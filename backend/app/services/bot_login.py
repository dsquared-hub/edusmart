"""Вход на сайт через бота.

1. Сайт: POST /api/auth/bot/start → токен, число для сверки и ссылка
   t.me/<бот>?start=login_<токен>.
2. Бот: человек открывает ссылку и нажимает то же число, что видит на сайте.
3. Сайт опрашивает POST /api/auth/bot/poll и, когда вход подтверждён,
   получает обычный токен сайта. Каждый запрос срабатывает один раз.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import utcnow
from app.db.models import LoginRequest, User
from app.services.accounts import AccountError, enter_as

TTL = timedelta(minutes=5)
PAYLOAD_PREFIX = "login_"
CHOICES = 3  # сколько чисел показывает бот (одно верное)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class StartedLogin:
    token: str
    match_code: int
    expires_at: datetime


async def start(session: AsyncSession, as_role: str | None = None) -> StartedLogin:
    now = utcnow()
    # Попутно чистим старые запросы — таблица не растёт
    await session.execute(delete(LoginRequest).where(LoginRequest.expires_at < now - timedelta(days=1)))
    token = secrets.token_urlsafe(24)  # 32 символа: влезает в deep link (≤ 64)
    request = LoginRequest(
        token_hash=_hash(token),
        match_code=10 + secrets.randbelow(90),
        status="pending",
        as_role=as_role,
        created_at=now,
        expires_at=now + TTL,
    )
    session.add(request)
    await session.commit()
    return StartedLogin(token, request.match_code, request.expires_at)


async def find_pending(session: AsyncSession, token: str) -> LoginRequest | None:
    """Запрос, который ещё можно подтвердить в боте."""
    request = await session.scalar(
        select(LoginRequest).where(LoginRequest.token_hash == _hash(token))
    )
    if request is None or request.status != "pending" or request.expires_at < utcnow():
        return None
    return request


def choices_for(request: LoginRequest) -> list[int]:
    """Верное число + случайные другие, в случайном порядке."""
    numbers = {request.match_code}
    while len(numbers) < CHOICES:
        numbers.add(10 + secrets.randbelow(90))
    result = list(numbers)
    secrets.SystemRandom().shuffle(result)
    return result


async def answer(
    session: AsyncSession, request_id: int, user: User, chosen: int | None
) -> str:
    """Ответ в боте: chosen — выбранное число, None — «Это не я».

    Возвращает: confirmed | rejected | wrong_code | not_mentor | expired.
    Неверное число отменяет запрос: подобрать его перебором нельзя.
    Роль по странице входа (as_role): на странице ментора ученик или родитель
    получают not_mentor, на обычной — человек без роли становится учеником.
    """
    request = await session.get(LoginRequest, request_id)
    if request is None or request.status != "pending" or request.expires_at < utcnow():
        return "expired"
    if chosen is None or chosen != request.match_code:
        request.status = "rejected"
        await session.commit()
        return "rejected" if chosen is None else "wrong_code"
    if request.as_role:
        db_user = await session.get(User, user.id)
        try:
            await enter_as(session, db_user, request.as_role)
        except AccountError:
            request.status = "not_mentor"
            await session.commit()
            return "not_mentor"
        user.role = db_user.role  # бот держит свою копию пользователя — роль уже есть
    request.status = "confirmed"
    request.user_id = user.id
    await session.commit()
    return "confirmed"


async def poll(session: AsyncSession, token: str) -> tuple[str, User | None]:
    """Статус для сайта: pending | expired | rejected | not_mentor | ok (+ пользователь)."""
    request = await session.scalar(
        select(LoginRequest).where(LoginRequest.token_hash == _hash(token))
    )
    if request is None:
        return "expired", None
    if request.status in ("rejected", "not_mentor"):
        return request.status, None
    if request.status == "pending":
        return ("expired", None) if request.expires_at < utcnow() else ("pending", None)
    if request.status != "confirmed" or request.user_id is None:
        return "expired", None  # уже использован
    # Условный UPDATE: два одновременных опроса не получат два входа
    result = await session.execute(
        update(LoginRequest)
        .where(LoginRequest.id == request.id, LoginRequest.status == "confirmed")
        .values(status="used")
    )
    await session.commit()
    if result.rowcount != 1:
        return "expired", None
    return "ok", await session.get(User, request.user_id)
