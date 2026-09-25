"""Сборка Dispatcher — общая для main.py и тестов."""
from __future__ import annotations

import logging

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from app.core.config import Settings
from app.services.explain import ExplainService
from bot.handlers import main_router
from bot.middlewares import DbUserMiddleware, FloodControlMiddleware, SecurityMiddleware
from bot.security import SecurityManager


def create_dispatcher(
    explain: ExplainService, settings: Settings, security: SecurityManager | None = None
) -> Dispatcher:
    # FSM хранит только «жду тему / жду код». Сами темы — в БД.
    dp = Dispatcher(storage=MemoryStorage())
    dp["explain"] = explain
    dp["settings"] = settings
    dp["security"] = security or SecurityManager(owner_id=settings.owner_id)

    # Первая зарегистрированная — самая внешняя
    dp.update.outer_middleware(SecurityMiddleware())
    dp.update.outer_middleware(
        FloodControlMiddleware(
            max_messages=settings.flood_max_messages,
            window_seconds=settings.flood_window_seconds,
        )
    )
    dp.update.outer_middleware(DbUserMiddleware())

    @dp.errors()
    async def on_error(event: ErrorEvent) -> None:
        logging.error("Необработанная ошибка: %r", event.exception, exc_info=event.exception)

    dp.include_router(main_router)
    return dp
