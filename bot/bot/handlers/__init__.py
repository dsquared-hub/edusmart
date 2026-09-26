"""Общий роутер: собирает все хендлеры бота."""
from __future__ import annotations

from aiogram import Router

from bot.handlers.access import router as access_router
from bot.handlers.journal import router as journal_router
from bot.handlers.language import router as language_router
from bot.handlers.owner import router as owner_router
from bot.handlers.parent import router as parent_router
from bot.handlers.profile import router as profile_router
from bot.handlers.registration import router as registration_router
from bot.handlers.reports import router as reports_router
from bot.handlers.start import router as start_router
from bot.handlers.student import router as student_router
from bot.handlers.support import router as support_router
from bot.handlers.teacher import router as teacher_router
from bot.handlers.web_login import router as web_login_router

main_router = Router()
# Команды владельца — до ученика: иначе «/block …» в режиме «жду тему»
# ушло бы в Gemini как тема.
for _router in (
    web_login_router,  # /start login_… — раньше обычного /start
    start_router,
    registration_router,
    language_router,
    owner_router,
    reports_router,
    journal_router,
    support_router,
    student_router,
    parent_router,
    teacher_router,
    access_router,
    profile_router,
):
    main_router.include_router(_router)
