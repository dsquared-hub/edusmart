"""Вход: Mini App (initData) и Telegram Login Widget, логин+код. Выход везде."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import api_error, current_user, get_session
from app.api.routers.me import me_payload
from app.api.schemas import CodeAuthIn, TelegramAuthIn
from app.core.config import get_settings
from app.core.security import (
    InvalidTelegramAuth,
    create_token,
    verify_init_data,
    verify_login_widget,
)
from app.db.models import User
from app.repositories.blocks import is_blocked
from app.services.accounts import (
    AccountError,
    enter_as,
    login_code,
    login_telegram,
    logout_everywhere,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _signed_in(session: AsyncSession, user: User) -> dict:
    return {
        "token": create_token(user.id, user.token_version or 0),
        "me": await me_payload(session, user),
    }


@router.post("/telegram")
async def auth_telegram(body: TelegramAuthIn, session: AsyncSession = Depends(get_session)):
    token = get_settings().bot_token
    try:
        if body.init_data:
            tg_user = verify_init_data(body.init_data, token)
        elif body.widget:
            tg_user = verify_login_widget(body.widget, token)
        else:
            raise InvalidTelegramAuth("Нет данных")
    except InvalidTelegramAuth:
        raise api_error(401, "bad_telegram_auth")
    if await is_blocked(session, int(tg_user["id"])):
        raise api_error(403, "blocked")
    user = await login_telegram(session, tg_user)
    try:
        await enter_as(session, user, body.as_role)
    except AccountError as exc:
        raise api_error(exc.status, exc.code)
    return await _signed_in(session, user)


@router.post("/code")
async def auth_code(body: CodeAuthIn, session: AsyncSession = Depends(get_session)):
    try:
        user = await login_code(session, body.login, body.code)
    except AccountError as exc:
        raise api_error(exc.status, exc.code)
    return await _signed_in(session, user)


@router.post("/logout")
async def logout(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    """Выход на всех устройствах: все выданные токены перестают работать."""
    await logout_everywhere(session, user)
    return {"ok": True}
