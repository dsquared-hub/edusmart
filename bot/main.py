"""Точка входа бота: общие сервисы из /backend, поллинг, планировщик, очередь событий."""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# `app` lives in the sibling backend directory when this file is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.core.config import get_settings
from app.db.session import SessionLocal, dispose_db, init_db
from app.services.explain import ExplainService
from app.services.gemini import make_lesson_provider
from bot.app_factory import create_dispatcher
from bot.events_worker import run_events_worker
from bot.scheduler import setup_scheduler
from bot.security import SecurityManager

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    settings = get_settings()
    if not settings.bot_token:
        raise SystemExit("BOT_TOKEN не задан в .env")
    if not settings.gemini_api_key and not settings.gemini_fake:
        raise SystemExit("GEMINI_API_KEY не задана в .env (или включи GEMINI_FAKE=1 для демо)")

    init_db()  # таблицы создаёт Alembic: `alembic upgrade head` в /backend

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    explain = ExplainService(make_lesson_provider(settings), settings)
    security = SecurityManager(owner_id=settings.owner_id)
    async with SessionLocal() as session:
        await security.refresh(session)  # бан-лист в память
    dp = create_dispatcher(explain, settings, security)

    scheduler = setup_scheduler(bot, settings.timezone)
    scheduler.start()
    worker = asyncio.create_task(run_events_worker(bot, settings.events_poll_seconds))
    logging.info("Бот запущен. Планировщик: %s", settings.timezone)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        worker.cancel()
        scheduler.shutdown(wait=False)
        await dispose_db()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit) as exc:
        if isinstance(exc, SystemExit) and exc.code:
            print(exc.code)
