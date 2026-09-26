"""Мидлвари на уровне update. Порядок регистрации (снаружи внутрь):

1. SecurityMiddleware — только личные чаты и бан-лист;
2. FloodControlMiddleware — не больше N апдейтов за окно;
3. DbUserMiddleware — пользователь из общей БД (заблокированный и флудер
   до базы не доходят).
"""
from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import Message, TelegramObject

from app.core.i18n import lang_from_telegram, set_current_lang, t
from app.db.session import SessionLocal
from app.repositories.users import upsert_telegram_user

logger = logging.getLogger(__name__)

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


def _inner(event: TelegramObject) -> TelegramObject:
    """Для Update реальный объект (Message / CallbackQuery / …) лежит в event.event."""
    return getattr(event, "event", None) or event


def _chat_of(event: TelegramObject):
    chat = getattr(event, "chat", None)
    if chat is None:
        message = getattr(event, "message", None)
        if message is not None:
            chat = message.chat
    return chat


class SecurityMiddleware(BaseMiddleware):
    """Отсекает группы/каналы и заблокированных. Заблокированному — одно
    уведомление не чаще раза в notify_interval секунд."""

    def __init__(self, notify_interval: float = 300.0):
        self.notify_interval = notify_interval
        self._notified: dict[int, float] = {}

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        inner = _inner(event)
        chat = _chat_of(inner)
        if chat is not None and chat.type != ChatType.PRIVATE:
            return None

        user = getattr(inner, "from_user", None)
        security = data.get("security")
        if user is None or security is None or not security.is_blocked(user.id):
            if len(self._notified) > 10_000:
                self._notified.clear()
            return await handler(event, data)

        now = time.monotonic()
        # Без значения по умолчанию 0.0: monotonic() считает от старта системы,
        # и на свежей машине (CI, новый сервер) первое уведомление потерялось бы.
        last = self._notified.get(user.id)
        if last is None or now - last > self.notify_interval:
            self._notified[user.id] = now
            bot = data.get("bot")
            if bot is not None and chat is not None:
                try:
                    lang = lang_from_telegram(getattr(user, "language_code", None))
                    await bot.send_message(chat.id, t("blocked_banner", lang))
                except Exception:  # noqa: BLE001
                    logger.exception("SECURITY: не удалось уведомить %s", user.id)
        return None


class FloodControlMiddleware(BaseMiddleware):
    """Отбрасывает апдейт, если от пользователя больше max_messages за window.
    Предупреждение — не чаще раза за 2 * window, чтобы не спамить в ответ."""

    def __init__(self, max_messages: int = 6, window_seconds: float = 3.0):
        self.max_messages = max_messages
        self.window = window_seconds
        self._history: dict[int, list[float]] = {}
        self._last_warning: dict[int, float] = {}

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        inner = _inner(event)
        user = getattr(inner, "from_user", None)
        if user is None:
            return await handler(event, data)

        now = time.monotonic()
        stamps = [s for s in self._history.get(user.id, []) if s >= now - self.window]
        stamps.append(now)
        self._history[user.id] = stamps

        if len(stamps) > self.max_messages:
            logger.warning("FLOOD: user=%s, %s событий за %.1fs", user.id, len(stamps), self.window)
            last = self._last_warning.get(user.id)
            if last is None or now - last > self.window * 2:
                self._last_warning[user.id] = now
                await self._warn(inner, data)
            return None

        if len(self._history) > 10_000:
            self._history.clear()
            self._last_warning.clear()
        return await handler(event, data)

    async def _warn(self, event: TelegramObject, data: dict[str, Any]) -> None:
        bot = data.get("bot")
        chat = _chat_of(event)
        if bot is None or chat is None:
            return
        key = "spam_slow" if isinstance(event, Message) else "spam_slow_callback"
        try:
            user = getattr(event, "from_user", None)
            lang = lang_from_telegram(getattr(user, "language_code", None))
            await bot.send_message(chat.id, t(key, lang), disable_notification=True)
        except Exception:  # noqa: BLE001 — нельзя ронять флуд-фильтр
            logger.exception("FLOOD: не удалось предупредить")


class DbUserMiddleware(BaseMiddleware):
    """Каждому апдейту — пользователь из общей БД (по Telegram ID) и его язык.

    Язык кладётся в ContextVar: t() в хендлерах и клавиатурах сама отвечает
    на языке пользователя. Новому пользователю язык берётся из Telegram.
    """

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is not None and not tg_user.is_bot:
            async with SessionLocal() as session:
                user = await upsert_telegram_user(
                    session,
                    tg_user.id,
                    tg_user.username,
                    tg_user.full_name,
                    lang=lang_from_telegram(tg_user.language_code),
                )
                await session.commit()
            data["user"] = user
            set_current_lang(user.lang)
        return await handler(event, data)
