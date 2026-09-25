"""JWT, проверка подписей Telegram и хэширование кодов входа."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from datetime import timedelta
from urllib.parse import parse_qsl

import jwt

from app.core.config import get_settings
from app.core.timeutil import utcnow

AUTH_MAX_AGE_SECONDS = 24 * 3600


class InvalidTelegramAuth(Exception):
    """Подпись Telegram не сошлась или данные устарели."""


# ---------- JWT ----------

def create_token(user_id: int, version: int = 0) -> str:
    """ver — версия токенов пользователя: выход/новый код увеличивают её,
    и все ранее выданные токены перестают приниматься."""
    settings = get_settings()
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "ver": version,
        "iat": now,
        "exp": now + timedelta(hours=settings.jwt_ttl_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> tuple[int, int] | None:
    """(user_id, версия) или None, если токен подделан/просрочен."""
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
        return int(payload["sub"]), int(payload.get("ver", 0))
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None


# ---------- Telegram ----------

def _check_fresh(auth_date: str | int | None, max_age: int) -> None:
    try:
        age = time.time() - int(auth_date)
    except (TypeError, ValueError):
        raise InvalidTelegramAuth("Нет auth_date")
    if age > max_age:
        raise InvalidTelegramAuth("Данные входа устарели")


def verify_login_widget(
    data: dict, bot_token: str, max_age: int = AUTH_MAX_AGE_SECONDS
) -> dict:
    """Telegram Login Widget: secret = SHA256(bot_token).

    https://core.telegram.org/widgets/login#checking-authorization
    """
    received_hash = data.get("hash")
    if not received_hash or not bot_token:
        raise InvalidTelegramAuth("Нет подписи")
    check_string = "\n".join(
        f"{k}={data[k]}" for k in sorted(data) if k != "hash" and data[k] is not None
    )
    secret = hashlib.sha256(bot_token.encode()).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, str(received_hash)):
        raise InvalidTelegramAuth("Подпись не совпала")
    _check_fresh(data.get("auth_date"), max_age)
    return data


def verify_init_data(
    init_data: str, bot_token: str, max_age: int = AUTH_MAX_AGE_SECONDS
) -> dict:
    """Mini App initData: secret = HMAC_SHA256("WebAppData", bot_token).

    Возвращает объект user из initData.
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    fields = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = fields.pop("hash", None)
    if not received_hash or not bot_token:
        raise InvalidTelegramAuth("Нет подписи")
    check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise InvalidTelegramAuth("Подпись не совпала")
    _check_fresh(fields.get("auth_date"), max_age)
    try:
        user = json.loads(fields["user"])
    except (KeyError, json.JSONDecodeError):
        raise InvalidTelegramAuth("Нет пользователя в initData")
    if "id" not in user:
        raise InvalidTelegramAuth("Нет id пользователя")
    return user


# ---------- Коды входа для учеников без Telegram ----------

def generate_access_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(code: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(code.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_code(code: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.scrypt(
        code.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1
    )
    return hmac.compare_digest(digest.hex(), digest_hex)
