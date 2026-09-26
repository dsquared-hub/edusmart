"""Регистрация взрослых в боте (по номеру телефона) и регистрация ими ребёнка.

Дети учатся в приложении (PWA), Telegram им не нужен: взрослый создаёт ребёнку
вход (логин + код) и передаёт его. Номер из «Поделиться контактом» Telegram уже
подтвердил — он нужен, чтобы вступить в семью ребёнка.
"""
from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import FamilyMember, User
from app.repositories.users import get_user
from app.services import families
from app.services.accounts import AccountError, IssuedAccess, create_child_access

ADULT_ROLES = ("parent", "teacher")
MIN_NAME, MAX_NAME = 2, 60
GRADES = range(5, 12)  # платформа — для 5–11 классов


def normalize_phone(raw: str) -> str:
    """«+998 90 123-45-67», «998901234567», «901234567» → «+998901234567»."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 9:
        digits = "998" + digits
    if not re.fullmatch(r"998\d{9}", digits):
        raise AccountError("reg_phone_not_uz")
    return "+" + digits


def clean_name(raw: str | None) -> str:
    name = " ".join((raw or "").split())
    if not (MIN_NAME <= len(name) <= MAX_NAME) or name.startswith("/"):
        raise AccountError("reg_bad_name")
    return name


async def register_adult(session: AsyncSession, user: User, raw_phone: str, role: str = "parent") -> User:
    """Регистрация в боте — одной кнопкой «Отправить номер». Номер из «Поделиться
    контактом» Telegram уже подтвердил. Уже зарегистрированный взрослый сохраняет роль
    (так он просто меняет номер); все остальные становятся родителями."""
    user = await get_user(session, user.id)
    if role not in ADULT_ROLES:
        raise AccountError("forbidden", 403)
    phone = normalize_phone(raw_phone)
    owner = await session.scalar(select(User).where(User.phone == phone))
    if owner is not None and owner.id != user.id:
        raise AccountError("reg_phone_taken", 409)
    if user.role not in ADULT_ROLES:
        user.role = role
    user.phone = phone
    await session.commit()
    return user


async def register_child(
    session: AsyncSession, adult: User, name: str, grade: int | None
) -> IssuedAccess:
    """Ребёнок + вход в приложение. Родитель: ребёнок входит в его семью, согласие —
    от родителя (отправляя имя ребёнка, он соглашается с политикой — об этом сказано
    в вопросе бота). Учитель: ученик ждёт согласия родителя."""
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
