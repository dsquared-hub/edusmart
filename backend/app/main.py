"""FastAPI: API сайта. Запуск: uvicorn app.main:app --reload"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.ratelimit import RateLimitMiddleware
from app.api.routers import (
    account, auth, avatar, explain, family, journal, me, push, support, teacher_checks, teacher_materials,
)
from app.services import web_push
from app.core.config import Settings, get_settings
from app.db.session import SessionLocal, dispose_db, init_db
from app.services.explain import ExplainService
from app.services.gemini import make_lesson_provider
from app.services.curriculum import ensure_sample
from app.services.questions import make_question_generator
from app.services.vision import make_work_checker
from app.services.work_checks import run_worker

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.jwt_secret == "change-me" or len(settings.jwt_secret) < 32:
        logging.warning("JWT_SECRET короткий или не задан — задай длинный случайный в .env")
    init_db()
    app.state.explain = ExplainService(make_lesson_provider(settings), settings)
    app.state.questions = make_question_generator(settings)
    if settings.curriculum_autoload:
        # Пустой каталог программы — образец, чтобы вечерний тест и ERS работали сразу
        try:
            async with SessionLocal() as session:
                await ensure_sample(session)
        except Exception:
            logging.exception("Не удалось загрузить образец программы (миграции применены?)")
    # Обработчик очереди ИИ-проверки работ (Модуль 5.1). В проде можно выключить
    # (CHECK_WORKER=0) и запускать отдельно: python -m app.workers
    workers = []
    if settings.check_worker:
        workers.append(asyncio.create_task(run_worker(make_work_checker(settings), settings)))
    # Web Push для PWA: доставка событий и напоминания о вечернем тесте без Telegram
    app.state.push = web_push.make_sender(settings)
    if settings.push_worker:
        workers.append(asyncio.create_task(web_push.run_worker(app.state.push)))
    yield
    for worker in workers:
        worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker
    await dispose_db()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Образовательная платформа — API", version="0.3.0", lifespan=lifespan)
    app.add_middleware(
        RateLimitMiddleware,
        auth=settings.rate_limit_auth,
        explain=settings.rate_limit_explain,
        api=settings.rate_limit_api,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(explain.router)
    app.include_router(journal.router)
    app.include_router(support.router)
    app.include_router(teacher_checks.router)
    app.include_router(teacher_materials.router)
    app.include_router(family.router)
    app.include_router(account.router)
    app.include_router(push.router)
    app.include_router(avatar.router)

    @app.get("/api/health")
    async def health():
        """Для мониторинга и docker healthcheck: API жив и база отвечает."""
        try:
            async with SessionLocal() as session:
                await session.execute(text("SELECT 1"))
        except Exception:
            logging.exception("Health: база недоступна")
            return JSONResponse({"ok": False, "db": False}, status_code=503)
        return {"ok": True, "db": True}

    return app


app = create_app()
