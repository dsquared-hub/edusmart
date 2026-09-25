"""PWA: подписка браузера на Web Push (уведомления без Telegram)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_session
from app.core.config import get_settings
from app.core.i18n import t
from app.db.models import User
from app.services import web_push

router = APIRouter(prefix="/api/v1/push", tags=["push"])


def get_push_sender(request: Request) -> web_push.PushSender | None:
    if not hasattr(request.app.state, "push"):
        request.app.state.push = web_push.make_sender()
    return request.app.state.push


@router.get("/key")
async def public_key():
    """Публичный VAPID-ключ для pushManager.subscribe (null — пуши выключены)."""
    key = get_settings().vapid_public_key
    return {"public_key": key or None}


class Keys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=200)
    auth: str = Field(min_length=8, max_length=100)


class SubscriptionIn(BaseModel):
    endpoint: str = Field(pattern=r"^https://", max_length=1000)  # push-сервисы браузеров — только HTTPS
    keys: Keys


@router.post("/subscribe")
async def subscribe(body: SubscriptionIn, request: Request, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await web_push.subscribe(session, user, body.endpoint, body.keys.p256dh, body.keys.auth, request.headers.get("user-agent"))
    return {"ok": True}


class EndpointIn(BaseModel):
    endpoint: str = Field(max_length=1000)


@router.post("/unsubscribe")
async def unsubscribe(body: EndpointIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await web_push.unsubscribe(session, user, body.endpoint)
    return {"ok": True}


@router.post("/test")
async def test_push(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    sender: web_push.PushSender | None = Depends(get_push_sender),
):
    """Пробное уведомление на все устройства пользователя (кнопка в профиле)."""
    if sender is None:
        raise HTTPException(503, detail={"code": "push_disabled"})
    lang = user.lang if user.lang in ("ru", "uz", "en") else "ru"
    delivered = await web_push.send_to(session, sender, user, web_push.Push(t("push_test_title", lang), t("push_test_body", lang), "/"))
    await session.commit()
    return {"delivered": delivered}
