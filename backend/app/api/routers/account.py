"""API Модуля 4: вход по номеру телефона (SMS) и семейный аккаунт."""
from __future__ import annotations

import io
from datetime import timezone
from typing import Callable, Literal

import segno
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_session
from app.api.routers.auth import _signed_in
from app.api.routers.me import me_payload
from app.core.config import get_settings
from app.db.models import User
from app.services import families, sms
from app.services.accounts import choose_role

router = APIRouter(prefix="/api/v1", tags=["account"])


def get_sms_sender(request: Request) -> sms.SmsSender:
    sender = getattr(request.app.state, "sms", None)
    if sender is None:
        sender = request.app.state.sms = sms.make_sender()
    return sender


def get_telegram_sender(request: Request) -> Callable[[int], sms.SmsSender]:
    """chat_id → отправитель кода через бота (в тестах подменяется в app.state)."""
    factory = getattr(request.app.state, "telegram_sms", None)
    return factory or (lambda chat_id: sms.TelegramSender(get_settings().bot_token, chat_id))


class SmsRequestIn(BaseModel):
    phone: str = Field(min_length=9, max_length=20)
    lang: Literal["ru", "uz", "en"] = "uz"
    # telegram — код от нашего бота, если номером поделились в боте (бесплатно, без SMS)
    channel: Literal["sms", "telegram"] = "sms"


@router.post("/auth/sms/request")
async def sms_request(
    body: SmsRequestIn,
    session: AsyncSession = Depends(get_session),
    sender: sms.SmsSender = Depends(get_sms_sender),
    telegram_sender: Callable[[int], sms.SmsSender] = Depends(get_telegram_sender),
):
    settings = get_settings()
    try:
        if body.channel == "telegram":
            chat_id = await sms.telegram_chat(session, body.phone) if settings.bot_token else None
            if chat_id is None:
                raise sms.SmsError("tg_not_linked", 409, bot_username=settings.bot_username or None)
            sender = telegram_sender(chat_id)
        phone = await sms.request_code(session, body.phone, sender, body.lang, settings)
    except sms.SmsError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, **exc.extra})
    return {"phone": phone, "ttl": settings.sms_code_ttl, "resend_after": settings.sms_resend_seconds}


class SmsVerifyIn(BaseModel):
    phone: str = Field(min_length=9, max_length=20)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


@router.post("/auth/sms/verify")
async def sms_verify(body: SmsVerifyIn, session: AsyncSession = Depends(get_session)):
    try:
        user = await sms.verify_code(session, body.phone, body.code)
    except sms.SmsError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, **exc.extra})
    return await _signed_in(session, user)


class RoleIn(BaseModel):
    role: Literal["student", "parent"]
    name: str | None = Field(None, max_length=100)
    grade: int | None = Field(None, ge=5, le=11)


@router.post("/me/role")
async def set_role(body: RoleIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    """Первый вход по SMS: выбор роли, имени и класса. Роль задаётся один раз."""
    if user.role is not None:
        raise HTTPException(409, detail={"code": "role_already_set"})
    if body.name and body.name.strip():
        user.full_name = body.name.strip()
    await choose_role(session, user, body.role)
    if body.role == "student" and body.grade:
        from app.repositories.students import get_student

        student = await get_student(session, user.id)
        student.grade = body.grade
        await session.commit()
    return await me_payload(session, user)


def _mask(phone: str | None) -> str | None:
    return f"{phone[:6]} ** *** {phone[-4:-2]} {phone[-2:]}" if phone else None


@router.get("/family")
async def get_family(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    settings = get_settings()
    family = await families.family_of(session, user)
    rows = await families.members(session, family.id) if family else []
    return {
        "family_id": family.id if family else None,
        "members": [
            {"user_id": u.id, "name": u.display_name, "role": m.member_role, "phone": _mask(u.phone), "me": u.id == user.id}
            for m, u in rows
        ],
        "limits": {"adults": settings.family_max_adults, "children": settings.family_max_children},
    }


@router.post("/family/invites")
async def create_invite(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    try:
        invite = await families.create_invite(session, user)
    except families.FamilyError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code})
    join_url = f"{get_settings().web_url.rstrip('/')}/family/join?code={invite.code}"
    svg = io.BytesIO()
    segno.make(join_url, error="m").save(svg, kind="svg", scale=6, border=2, dark="#2b263a", light=None)
    return {
        "code": invite.code,
        "expires_at": invite.expires_at.replace(tzinfo=timezone.utc).isoformat(),
        "join_url": join_url,
        "qr_svg": svg.getvalue().decode(),
    }


class JoinIn(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


@router.post("/family/join")
async def join_family(body: JoinIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    try:
        family = await families.join(session, user, body.code)
    except families.FamilyError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code})
    return {"family_id": family.id}
