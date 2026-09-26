"""Регистрация взрослых в боте (родитель / учитель) и регистрация ими ребёнка.

Дети учатся в приложении (PWA), Telegram им не нужен: взрослый создаёт ребёнку
вход (логин + код) и передаёт его. Номер из «Поделиться контактом» Telegram уже
подтвердил — с ним взрослый входит на сайт по SMS в тот же аккаунт.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import FamilyMember, User
from app.repositories.users import get_user
from app.services import families
from app.services.accounts import AccountError, IssuedAccess, create_child_access
from app.services.sms import SmsError, normalize_phone

ADULT_ROLES = ("parent", "teacher")
MIN_NAME, MAX_NAME = 2, 60
GRADES = range(1, 12)


def clean_name(raw: str | None) -> str:
    name = " ".join((raw or "").split())
    if not (MIN_NAME <= len(name) <= MAX_NAME) or name.startswith("/"):
        raise AccountError("reg_bad_name")
    return name


async def set_name(session: AsyncSession, user: User, full_name: str) -> User:
    """Шаг регистрации взрослого: как к нему обращаться (роль уже выбрана кнопкой)."""
    user = await get_user(session, user.id)
    if user.role not in ADULT_ROLES:
        raise AccountError("forbidden", 403)
    user.full_name = clean_name(full_name)
    await session.commit()
    return user


async def attach_phone(session: AsyncSession, user: User, raw: str) -> str:
    """Номер из «Поделиться контактом» — Telegram уже подтвердил, что он принадлежит пользователю."""
    user = await get_user(session, user.id)
    if user.role not in ADULT_ROLES:
        raise AccountError("forbidden", 403)
    try:
        phone = normalize_phone(raw)
    except SmsError:
        raise AccountError("reg_phone_not_uz") from None
    owner = await session.scalar(select(User).where(User.phone == phone))
    if owner is not None and owner.id != user.id:
        raise AccountError("reg_phone_taken", 409)
    user.phone = phone
    await session.commit()
    return phone


async def register_child(
    session: AsyncSession, adult: User, name: str, grade: int | None
) -> IssuedAccess:
    """Ребёнок + вход в приложение. Родитель: ребёнок входит в его семью, согласие —
    от родителя (он подтвердил его кнопкой перед регистрацией). Учитель: ученик ждёт
    согласия родителя."""
    adult = await get_user(session, adult.id)
    if adult.role not in ADULT_ROLES:
        raise AccountError("forbidden", 403)
    name = clean_name(name)
    if grade is not None and grade not in GRADES:
        raise AccountError("reg_bad_grade")

    family = None
    if adult.role == "parent":
        family = await families.ensure_family(session, adult)
        children = await session.scalar(
            select(func.count()).select_from(FamilyMember).where(
                FamilyMember.family_id == family.id,
                FamilyMember.member_role == "student",
                FamilyMember.status == "active",
            )
        )
        if children >= get_settings().family_max_children:
            raise AccountError("family_full_children", 409)

    issued = await create_child_access(session, adult, name, grade=grade)
    if family is not None:
        session.add(FamilyMember(family_id=family.id, user_id=issued.user.id, member_role="student", status="active"))
        await session.flush()
        await families.sync_links(session, family.id)  # второй родитель семьи тоже видит ребёнка
        await session.commit()
    return issued
