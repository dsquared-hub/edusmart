"""Вход по номеру телефона (+998) с одноразовым SMS-кодом (Модуль 4, п. 2.1).

Код — 6 цифр, живёт 5 минут, не больше 5 попыток. В БД — только HMAC кода с
секретом сервера (6 цифр иначе подбираются по хэшу мгновенно). Повторная отправка —
не чаще раза в минуту и не больше 5 SMS в час на номер: защита от «SMS-бомбинга»
и от лишних расходов на шлюз.

Шлюз: Eskiz.uz (SMS_PROVIDER=eskiz, нужен одобренный шаблон текста) или log —
код пишется в лог сервера (разработка).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
import time
from datetime import timedelta
from typing import Protocol

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.timeutil import utcnow
from app.db.models import SmsCode, User

log = logging.getLogger(__name__)

TEXT = {
    "ru": "EDU ProgressUZ: код для входа {code}. Никому не сообщайте его.",
    "uz": "EDU ProgressUZ: kirish kodi {code}. Uni hech kimga aytmang.",
    "en": "EDU ProgressUZ: your login code is {code}. Don't share it.",
}


class SmsError(Exception):
    def __init__(self, code: str, status: int = 400, **extra):
        super().__init__(code)
        self.code = code
        self.status = status
        self.extra = extra


def normalize_phone(raw: str) -> str:
    """«+998 90 123-45-67», «998901234567», «901234567» → «+998901234567»."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 9:
        digits = "998" + digits
    if not re.fullmatch(r"998\d{9}", digits):
        raise SmsError("bad_phone", 422)
    return "+" + digits


def _hash(phone: str, code: str, settings: Settings) -> str:
    return hmac.new(settings.jwt_secret.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


class SmsSender(Protocol):
    async def send(self, phone: str, text: str) -> None: ...


class LogSender:
    """Разработка: SMS не уходит, код — в лог сервера."""

    async def send(self, phone: str, text: str) -> None:
        log.warning("SMS (не отправлено, SMS_PROVIDER=log) %s: %s", phone, text)


class MemorySender:
    """Тесты: запоминаем отправленные SMS."""

    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    async def send(self, phone: str, text: str) -> None:
        self.sent.append((phone, text))


class EskizSender:
    """Eskiz.uz: токен по логину/паролю (живёт ~30 дней), затем отправка SMS."""

    BASE = "https://notify.eskiz.uz/api"

    def __init__(self, settings: Settings):
        self.settings = settings
        self._token: str | None = None
        self._token_at = 0.0

    async def _auth(self, client) -> str:
        if self._token and time.time() - self._token_at < 25 * 24 * 3600:
            return self._token
        r = await client.post(f"{self.BASE}/auth/login", data={"email": self.settings.eskiz_email, "password": self.settings.eskiz_password})
        r.raise_for_status()
        self._token, self._token_at = r.json()["data"]["token"], time.time()
        return self._token

    async def send(self, phone: str, text: str) -> None:
        import httpx

        async with httpx.AsyncClient(timeout=15) as client:
            token = await self._auth(client)
            r = await client.post(
                f"{self.BASE}/message/sms/send",
                headers={"Authorization": f"Bearer {token}"},
                data={"mobile_phone": phone.lstrip("+"), "message": text, "from": self.settings.eskiz_from},
            )
            if r.status_code == 401:  # токен истёк раньше срока — один повтор
                self._token = None
                token = await self._auth(client)
                r = await client.post(
                    f"{self.BASE}/message/sms/send",
                    headers={"Authorization": f"Bearer {token}"},
                    data={"mobile_phone": phone.lstrip("+"), "message": text, "from": self.settings.eskiz_from},
                )
            r.raise_for_status()


def make_sender(settings: Settings | None = None) -> SmsSender:
    settings = settings or get_settings()
    if settings.sms_provider == "eskiz":
        return EskizSender(settings)
    return LogSender()


async def request_code(
    session: AsyncSession, raw_phone: str, sender: SmsSender, lang: str = "ru", settings: Settings | None = None
) -> str:
    settings = settings or get_settings()
    phone = normalize_phone(raw_phone)
    now = utcnow()
    last = await session.scalar(select(SmsCode).where(SmsCode.phone == phone).order_by(desc(SmsCode.created_at)))
    if last is not None and (now - last.created_at).total_seconds() < settings.sms_resend_seconds:
        wait = settings.sms_resend_seconds - int((now - last.created_at).total_seconds())
        raise SmsError("sms_too_soon", 429, retry_after=wait)
    hour = await session.scalar(
        select(func.count(SmsCode.id)).where(SmsCode.phone == phone, SmsCode.created_at >= now - timedelta(hours=1))
    )
    if (hour or 0) >= settings.sms_hourly_limit:
        raise SmsError("sms_limit", 429)
    code = f"{secrets.randbelow(1_000_000):06d}"
    session.add(SmsCode(
        phone=phone, code_hash=_hash(phone, code, settings), attempts=0, created_at=now,
        expires_at=now + timedelta(seconds=settings.sms_code_ttl),
    ))
    await session.commit()
    try:
        await sender.send(phone, TEXT.get(lang, TEXT["ru"]).format(code=code))
    except Exception as exc:
        log.exception("SMS на %s не отправлено", phone)
        raise SmsError("sms_send_failed", 502) from exc
    return phone


async def verify_code(session: AsyncSession, raw_phone: str, code: str, settings: Settings | None = None) -> User:
    """Проверка кода → пользователь с этим номером (новый номер — новый пользователь без роли)."""
    settings = settings or get_settings()
    phone = normalize_phone(raw_phone)
    record = await session.scalar(
        select(SmsCode).where(SmsCode.phone == phone, SmsCode.used_at.is_(None)).order_by(desc(SmsCode.created_at))
    )
    if record is None or record.expires_at < utcnow():
        raise SmsError("sms_expired", 410)
    if record.attempts >= settings.sms_max_attempts:
        raise SmsError("sms_locked", 429)
    if not hmac.compare_digest(record.code_hash, _hash(phone, (code or "").strip(), settings)):
        record.attempts += 1
        await session.commit()
        left = settings.sms_max_attempts - record.attempts
        raise SmsError("sms_wrong" if left > 0 else "sms_locked", 401 if left > 0 else 429, attempts_left=max(0, left))
    record.used_at = utcnow()
    user = await session.scalar(select(User).where(User.phone == phone))
    if user is None:
        user = User(phone=phone, lang="uz")
        session.add(user)
    await session.commit()
    return user
