"""Отдельный обработчик очереди ИИ-проверки работ.

    python -m app.workers

Для прода: API запускается с CHECK_WORKER=0, а обработчиков — столько, сколько
нужно под нагрузку (в PostgreSQL они не мешают друг другу: SKIP LOCKED).
"""
from __future__ import annotations

import asyncio
import logging

from app.core.config import get_settings
from app.db.session import dispose_db, init_db
from app.services.vision import make_work_checker
from app.services.work_checks import run_worker


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    init_db()
    try:
        await run_worker(make_work_checker(settings), settings)
    finally:
        await dispose_db()


if __name__ == "__main__":
    asyncio.run(main())
