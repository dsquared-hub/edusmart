"""API Модуля 4: семейный аккаунт (приглашения, вступление, состав семьи)."""
from __future__ import annotations

import io
from datetime import timezone

import segno
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_session
from app.core.config import get_settings
from app.db.models import User
from app.services import families

router = APIRouter(prefix="/api/v1", tags=["account"])


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
