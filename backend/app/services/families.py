"""Семейный аккаунт (Модуль 4, п. 2.1): «многие ко многим» через семью.

У ребёнка может быть несколько взрослых (мама, папа, опекун), у взрослого — несколько
детей: все взрослые семьи видят всех её детей. Лимиты: до 4 взрослых и 6 детей.
Привязка — код из 6 цифр или QR (24 часа, один раз); взрослый, который вступает в
семью, должен поделиться номером телефона в боте. Доступ к данным детей остаётся на
связях parent_links (их используют журнал, отчёты, бот) — семья их поддерживает.
"""
from __future__ import annotations

import secrets
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.timeutil import utcnow
from app.db.models import Family, FamilyInvite, FamilyMember, User
from app.repositories.students import get_student, link_parent

ADULT_ROLES = ("parent", "guardian")


class FamilyError(Exception):
    def __init__(self, code: str, status: int = 409):
        super().__init__(code)
        self.code = code
        self.status = status


def member_role_for(user: User) -> str:
    if user.role == "student":
        return "student"
    if user.role == "parent":
        return "parent"
    raise FamilyError("family_role_required", 403)  # учитель и пользователь без роли — не члены семьи


async def family_of(session: AsyncSession, user: User) -> Family | None:
    member = await session.scalar(select(FamilyMember).where(FamilyMember.user_id == user.id, FamilyMember.status == "active"))
    return await session.get(Family, member.family_id) if member else None


async def ensure_family(session: AsyncSession, user: User) -> Family:
    family = await family_of(session, user)
    if family is not None:
        return family
    family = Family(name=None)
    session.add(family)
    await session.flush()
    session.add(FamilyMember(family_id=family.id, user_id=user.id, member_role=member_role_for(user), status="active"))
    await session.flush()
    return family


async def members(session: AsyncSession, family_id: int) -> list[tuple[FamilyMember, User]]:
    rows = await session.execute(
        select(FamilyMember, User).join(User, User.id == FamilyMember.user_id)
        .where(FamilyMember.family_id == family_id, FamilyMember.status == "active")
        .order_by(FamilyMember.created_at)
    )
    return [(m, u) for m, u in rows.all()]


async def create_invite(session: AsyncSession, user: User, settings: Settings | None = None) -> FamilyInvite:
    settings = settings or get_settings()
    member_role_for(user)
    family = await ensure_family(session, user)
    for _ in range(20):
        code = f"{secrets.randbelow(1_000_000):06d}"
        if not await session.scalar(select(FamilyInvite.id).where(FamilyInvite.code == code)):
            break
    else:  # pragma: no cover — 20 совпадений подряд практически невозможны
        raise FamilyError("try_again", 503)
    invite = FamilyInvite(
        family_id=family.id, code=code, created_by=user.id, expires_at=utcnow() + timedelta(hours=settings.family_invite_hours)
    )
    session.add(invite)
    await session.commit()
    return invite


async def join(session: AsyncSession, user: User, code: str, settings: Settings | None = None) -> Family:
    settings = settings or get_settings()
    role = member_role_for(user)
    if role in ADULT_ROLES and not user.phone:
        raise FamilyError("phone_required", 403)  # номер — кнопкой «Поделиться номером» в боте
    invite = await session.scalar(select(FamilyInvite).where(FamilyInvite.code == (code or "").strip()))
    if invite is None or invite.used_at is not None or invite.expires_at < utcnow():
        raise FamilyError("invite_invalid", 404)
    current = await family_of(session, user)
    if current is not None:
        if current.id == invite.family_id:
            raise FamilyError("already_in_family", 409)
        raise FamilyError("in_other_family", 409)

    counts = dict(
        (await session.execute(
            select(FamilyMember.member_role, func.count())
            .where(FamilyMember.family_id == invite.family_id, FamilyMember.status == "active")
            .group_by(FamilyMember.member_role)
        )).all()
    )
    adults = sum(counts.get(r, 0) for r in ADULT_ROLES)
    if role in ADULT_ROLES and adults >= settings.family_max_adults:
        raise FamilyError("family_full_adults", 409)
    if role == "student" and counts.get("student", 0) >= settings.family_max_children:
        raise FamilyError("family_full_children", 409)

    session.add(FamilyMember(family_id=invite.family_id, user_id=user.id, member_role=role, status="active"))
    invite.used_by, invite.used_at = user.id, utcnow()
    await session.flush()
    await sync_links(session, invite.family_id)
    await session.commit()
    return await session.get(Family, invite.family_id)


async def sync_links(session: AsyncSession, family_id: int) -> None:
    """Каждый взрослый семьи связан с каждым её ребёнком (parent_links)."""
    rows = await members(session, family_id)
    adults = [u for m, u in rows if m.member_role in ADULT_ROLES]
    children = [u for m, u in rows if m.member_role == "student"]
    for child in children:
        if await get_student(session, child.id) is None:
            continue
        for adult in adults:
            await link_parent(session, adult.id, child.id)
