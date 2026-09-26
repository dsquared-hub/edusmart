from __future__ import annotations

from typing import AsyncIterator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.models import User
from app.db.session import SessionLocal
from app.repositories.blocks import is_blocked
from app.services.explain import ExplainService

bearer = HTTPBearer(auto_error=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def get_explain(request: Request) -> ExplainService:
    return request.app.state.explain


def get_work_checker(request: Request):
    """Vision-проверка фото работ (квесты ученика). Создаётся один раз на приложение."""
    checker = getattr(request.app.state, "work_checker", None)
    if checker is None:
        from app.services.vision import make_work_checker

        checker = request.app.state.work_checker = make_work_checker()
    return checker


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    decoded = decode_token(credentials.credentials) if credentials else None
    user = await session.get(User, decoded[0]) if decoded else None
    # Версия не совпала — пользователь вышел везде или родитель выдал новый код
    if user is None or decoded[1] != (user.token_version or 0):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "unauthorized"})
    # Бан владельца бота действует и на сайте
    if await is_blocked(session, user.telegram_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "blocked"})
    return user


def api_error(status_code: int, code: str) -> HTTPException:
    """Ошибки API: {"detail": {"code": "..."}} — фронт переводит код в текст."""
    return HTTPException(status_code, detail={"code": code})
