"""Профиль, настройки оформления, прогресс."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import api_error, current_user, get_explain, get_session
from app.api.schemas import SettingsIn
from app.core.config import get_settings
from app.db.models import User
from app.repositories import topics as topics_repo
from app.repositories.students import completed_count, get_student
from app.services.accounts import AccountError, consent_is_current, update_settings
from app.services.explain import ExplainService
from app.services.gamification import level_for, level_progress, points_to_next_level

router = APIRouter(prefix="/api", tags=["me"])


async def me_payload(session: AsyncSession, user: User) -> dict:
    student = await get_student(session, user.id) if user.role == "student" else None
    return {
        "id": user.id,
        "name": user.display_name,
        "role": user.role,
        "has_telegram": user.telegram_id is not None,
        "login": user.login,
        "settings": {
            "theme": user.theme,
            "high_contrast": user.high_contrast,
            "dyslexia_font": user.dyslexia_font,
            "lang": user.lang,
        },
        "student": {
            "points": student.points,
            "level": level_for(student.points),
            "streak": student.streak,
            "consent_confirmed": consent_is_current(student),
            "family_code": student.family_code,
            "grade": student.grade,
        }
        if student
        else None,
    }


def _topic_brief(topic) -> dict:
    return {
        "id": topic.id,
        "title": topic.title,
        "subject": topic.subject,
        "status": topic.status,
        "source": topic.source,
        "current_step": topic.current_step,
        "total_steps": topic.total_steps,
        "points_earned": topic.points_earned,
        "updated_at": topic.updated_at.isoformat() if topic.updated_at else None,
        "completed_at": topic.completed_at.isoformat() if topic.completed_at else None,
    }


@router.get("/me")
async def get_me(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    return await me_payload(session, user)


@router.patch("/me/settings")
async def patch_settings(
    body: SettingsIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        await update_settings(session, user, **body.model_dump(exclude_none=True))
    except AccountError as exc:
        raise api_error(exc.status, exc.code)
    return await me_payload(session, user)


@router.get("/progress")
async def get_progress(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    explain: ExplainService = Depends(get_explain),
):
    student = await get_student(session, user.id)
    if student is None:
        raise api_error(403, "not_student")
    return {
        "points": student.points,
        "level": level_for(student.points),
        "level_progress": level_progress(student.points),
        "points_to_next_level": points_to_next_level(student.points),
        "streak": student.streak,
        "topics_completed": await completed_count(session, user.id),
        "explanations_left_today": await explain.remaining_today(session, user.id),
        "daily_limit": explain.settings.daily_explain_limit,
        "in_progress": [_topic_brief(t) for t in await topics_repo.list_in_progress(session, user.id)],
        "recent": [_topic_brief(t) for t in await topics_repo.list_completed(session, user.id, 10)],
    }


@router.get("/config")
async def public_config():
    """Публичные настройки для фронта (имя бота для Login Widget)."""
    settings = get_settings()
    return {
        "bot_username": settings.bot_username,
        "daily_limit": settings.daily_explain_limit,
        "points_per_step": settings.points_per_step,
        "points_second_try": settings.points_second_try,
        "max_photo_mb": settings.max_photo_mb,
        # Для страницы политики конфиденциальности
        "policy_version": settings.policy_version,
        "operator_name": settings.operator_name,
        "operator_contact": settings.operator_contact,
        "data_location": settings.data_location,
    }
