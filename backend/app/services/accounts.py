"""Аккаунты: вход (Telegram / логин+код), роли, привязки, согласие, настройки."""
from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import lang_from_telegram
from app.core.security import generate_access_code, hash_code, verify_code
from app.core.timeutil import utcnow
from app.core.config import get_settings
from app.db.models import ROLES, THEMES, ConsentRecord, Student, User
from app.repositories import students as students_repo
from app.repositories import users as users_repo

MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15

_TRANSLIT = dict(
    zip(
        "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
        ["a", "b", "v", "g", "d", "e", "yo", "zh", "z", "i", "y", "k", "l", "m", "n", "o",
         "p", "r", "s", "t", "u", "f", "kh", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"],
    )
)


class AccountError(Exception):
    code = "account_error"
    status = 400

    def __init__(self, code: str | None = None, status: int | None = None):
        super().__init__(code or self.code)
        if code:
            self.code = code
        if status:
            self.status = status


@dataclass
class IssuedAccess:
    student: Student
    user: User
    login: str
    code: str  # показываем один раз — в БД только хэш


# ---------- Вход ----------

async def login_telegram(session: AsyncSession, tg_user: dict) -> User:
    """Один и тот же пользователь для бота, Login Widget и Mini App."""
    full_name = " ".join(
        p for p in (tg_user.get("first_name"), tg_user.get("last_name")) if p
    ) or None
    user = await users_repo.upsert_telegram_user(
        session,
        int(tg_user["id"]),
        tg_user.get("username"),
        full_name,
        lang=lang_from_telegram(tg_user.get("language_code")),
    )
    await session.commit()
    return user


async def login_code(session: AsyncSession, login: str, code: str) -> User:
    user = await users_repo.get_by_login(session, login.strip())
    if user is None:
        raise AccountError("bad_credentials", 401)
    now = utcnow()
    if user.locked_until and user.locked_until > now:
        raise AccountError("login_locked", 429)
    if not verify_code(code.strip(), user.access_code_hash):
        user.failed_logins = (user.failed_logins or 0) + 1
        if user.failed_logins >= MAX_FAILED_LOGINS:
            user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
            user.failed_logins = 0
        await session.commit()
        raise AccountError("bad_credentials", 401)
    user.failed_logins = 0
    user.locked_until = None
    await session.commit()
    return user


# ---------- Роли и привязки ----------

async def choose_role(session: AsyncSession, user: User, role: str) -> User:
    if role not in ROLES:
        raise AccountError("bad_role")
    user.role = role
    if role == "student" and await students_repo.get_student(session, user.id) is None:
        await students_repo.create_student(session, user.id)
    await session.commit()
    return user


async def enter_as_mentor(session: AsyncSession, user: User) -> User:
    """Вход со страницы ментора: без роли — становится ментором (учителем),
    ученика и родителя не пускаем — у них свой вход."""
    if user.role is None:
        user.role = "teacher"
        await session.commit()
    elif user.role != "teacher":
        raise AccountError("not_mentor", 403)
    return user


async def enter_as_student(session: AsyncSession, user: User) -> User:
    """Вход через Telegram на обычной странице — это вход ученика.

    Без роли — становится учеником. «Родитель» без привязанных детей — почти
    всегда ребёнок, случайно выбравший не ту роль в боте: тоже делаем учеником.
    Настоящего родителя (есть дети) и ментора не трогаем.
    """
    if user.role is None or (
        user.role == "parent" and not await students_repo.get_children(session, user.id)
    ):
        await choose_role(session, user, "student")
    return user


async def enter_as(session: AsyncSession, user: User, role: str | None) -> User:
    """Роль по странице входа: teacher — страница ментора, student — обычная."""
    if role == "teacher":
        return await enter_as_mentor(session, user)
    if role == "student":
        return await enter_as_student(session, user)
    return user


async def link_by_family_code(
    session: AsyncSession, linker: User, code: str, as_role: str
) -> tuple[Student, bool]:
    """Привязка родителя/учителя по 6-значному коду ученика. (ученик, создана_ли)."""
    code = code.strip()
    if not (code.isdigit() and len(code) == 6):
        raise AccountError("code_invalid")
    student = await students_repo.get_student_by_code(session, code)
    if student is None:
        raise AccountError("code_not_found", 404)
    if as_role == "parent":
        created = await students_repo.link_parent(session, linker.id, student.user_id)
    else:
        created = await students_repo.link_teacher(session, linker.id, student.user_id)
    await session.commit()
    return student, created


def consent_is_current(student: Student, policy_version: str | None = None) -> bool:
    """Согласие дано на текущую версию политики. Единая проверка для API, бота и рассылок:
    после смены POLICY_VERSION старое согласие не считается.
    В демо-режиме (DEMO_MODE=1 или GEMINI_FAKE=1) согласие родителя не требуется."""
    settings = get_settings()
    if not settings.parent_consent_required:
        return True
    version = policy_version or settings.policy_version
    return bool(student.consent_confirmed and student.consent_version == version)


def _grant_consent(session: AsyncSession, parent: User, student: Student, channel: str) -> None:
    """Согласие на текущую версию политики + запись в журнал согласий."""
    version = get_settings().policy_version
    student.consent_confirmed = True
    student.consent_version = version
    session.add(
        ConsentRecord(
            parent_user_id=parent.id,
            parent_telegram_id=parent.telegram_id,
            student_user_id=student.user_id,
            policy_version=version,
            action="granted",
            channel=channel,
        )
    )


async def confirm_consent_for_children(
    session: AsyncSession, parent: User, channel: str = "bot"
) -> int:
    children = await students_repo.get_children(session, parent.id)
    for child in children:
        _grant_consent(session, parent, child, channel)
    await session.commit()
    return len(children)


async def delete_student_data(
    session: AsyncSession, parent: User, student_user_id: int, channel: str = "bot"
) -> str:
    """Родитель удаляет все данные ребёнка: аккаунт, прогресс, темы, привязки.

    Остаётся только запись в журнале согласий (кто и когда удалил) — это
    доказательство для проверяющих органов, в ней нет содержимого уроков.
    Возвращает имя ребёнка для сообщения.
    """
    if not await students_repo.is_linked_parent(session, parent.id, student_user_id):
        raise AccountError("forbidden", 403)
    user = await users_repo.get_user(session, student_user_id)
    name = user.display_name
    session.add(
        ConsentRecord(
            parent_user_id=parent.id,
            parent_telegram_id=parent.telegram_id,
            student_user_id=student_user_id,
            policy_version=get_settings().policy_version,
            action="deleted",
            channel=channel,
        )
    )
    await session.delete(user)  # ON DELETE CASCADE: ученик, привязки, темы, счётчики
    await session.commit()
    return name


# ---------- Ученики без Telegram ----------

def _slug(name: str) -> str:
    first = (name.strip().split() or ["kid"])[0].lower()
    out = "".join(_TRANSLIT.get(ch, ch) for ch in first)
    out = re.sub(r"[^a-z0-9]", "", out)[:12]
    return out or "kid"


async def _unique_login(session: AsyncSession, name: str) -> str:
    base = _slug(name)
    for _ in range(200):
        candidate = f"{base}{secrets.randbelow(900) + 100}"
        if not await users_repo.login_exists(session, candidate):
            return candidate
    raise AccountError("login_generation_failed", 500)


async def create_child_access(
    session: AsyncSession, issuer: User, child_name: str, grade: int | None = None
) -> IssuedAccess:
    """Родитель или учитель создаёт ученику вход без Telegram.

    Родитель — сразу даёт согласие (он и создаёт аккаунт).
    Учитель — ученик ждёт согласия родителя, как и раньше.
    """
    if issuer.role not in ("parent", "teacher"):
        raise AccountError("forbidden", 403)
    name = child_name.strip()[:255]
    if not name:
        raise AccountError("name_required")
    login = await _unique_login(session, name)
    code = generate_access_code()
    user = User(
        full_name=name,
        role="student",
        login=login,
        access_code_hash=hash_code(code),
        code_issued_by=issuer.id,
    )
    session.add(user)
    await session.flush()
    student = await students_repo.create_student(session, user.id, grade=grade)
    if issuer.role == "parent":
        await students_repo.link_parent(session, issuer.id, user.id)
        _grant_consent(session, issuer, student, "bot")
    else:
        await students_repo.link_teacher(session, issuer.id, user.id)
    await session.commit()
    return IssuedAccess(student, user, login, code)


async def regenerate_code(
    session: AsyncSession, issuer: User, student_user_id: int
) -> IssuedAccess:
    """Новый код входа (старый перестаёт работать). Только для своих учеников."""
    linked = await students_repo.is_linked_parent(
        session, issuer.id, student_user_id
    ) or await students_repo.is_linked_teacher(session, issuer.id, student_user_id)
    if not linked:
        raise AccountError("forbidden", 403)
    user = await users_repo.get_user(session, student_user_id)
    student = await students_repo.get_student(session, student_user_id)
    if user.login is None:
        user.login = await _unique_login(session, user.display_name)
    code = generate_access_code()
    user.access_code_hash = hash_code(code)
    user.code_issued_by = issuer.id
    user.failed_logins = 0
    user.locked_until = None
    user.token_version = (user.token_version or 0) + 1  # старые входы на сайт перестают работать
    await session.commit()
    return IssuedAccess(student, user, user.login, code)


async def issue_own_access(session: AsyncSession, adult: User) -> tuple[str, str]:
    """Логин и код для входа взрослого на сайт — выдаёт бот после регистрации
    и по кнопке «Вход на сайт». Логин постоянный, код каждый раз новый (старый
    перестаёт работать); уже открытые сессии не сбрасываются — для этого «Выйти везде»."""
    if adult.role not in ("parent", "teacher"):
        raise AccountError("forbidden", 403)
    if adult.login is None:
        adult.login = await _unique_login(session, adult.display_name)
    code = generate_access_code()
    adult.access_code_hash = hash_code(code)
    adult.failed_logins = 0
    adult.locked_until = None
    await session.commit()
    return adult.login, code


async def logout_everywhere(session: AsyncSession, user: User) -> None:
    """Отзывает все выданные токены сайта этого пользователя."""
    user.token_version = (user.token_version or 0) + 1
    await session.commit()


# ---------- Настройки сайта ----------

async def update_settings(
    session: AsyncSession,
    user: User,
    *,
    theme: str | None = None,
    high_contrast: bool | None = None,
    dyslexia_font: bool | None = None,
    lang: str | None = None,
) -> User:
    if theme is not None:
        if theme not in THEMES:
            raise AccountError("bad_theme")
        user.theme = theme
    if high_contrast is not None:
        user.high_contrast = high_contrast
    if dyslexia_font is not None:
        user.dyslexia_font = dyslexia_font
    if lang is not None:
        user.lang = lang
    await session.commit()
    return user
