"""«Не понял тему» на сайте — тот же ExplainService, что и в боте."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import api_error, current_user, get_explain, get_session
from app.api.schemas import AnswerIn, ReportIn
from app.core.i18n import t
from app.db.models import User
from app.services.explain import ExplainError, ExplainService, topic_public
from app.services.gamification import level_for
from app.services.gemini import SUBJECTS

router = APIRouter(prefix="/api/explain", tags=["explain"])

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}


def _raise(exc: ExplainError):
    """Ошибка сценария → HTTP. Для stale_step/topic_closed отдаём актуальную тему."""
    detail = {"code": exc.code}
    if exc.topic is not None:
        detail["topic"] = topic_public(exc.topic)
    raise HTTPException(exc.status, detail=detail)


async def _read_photo(photo: UploadFile | None, max_mb: int) -> tuple[bytes | None, str | None]:
    """Фото читается в память и отдаётся модели. На диск и в БД не пишется."""
    if photo is None or not photo.filename:
        return None, None
    if photo.content_type not in ALLOWED_MIME:
        raise api_error(415, "bad_photo_type")
    limit = max_mb * 1024 * 1024
    data = await photo.read(limit + 1)
    await photo.close()
    if len(data) > limit:
        raise api_error(413, "photo_too_large")
    return data or None, photo.content_type


@router.post("")
async def start_explain(
    title: str = Form(""),
    subject: str | None = Form(None),
    grade: int | None = Form(None, ge=1, le=11),
    photo: UploadFile | None = File(None),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    explain: ExplainService = Depends(get_explain),
):
    title = title.strip()
    if subject is not None and subject not in SUBJECTS:
        raise api_error(422, "bad_subject")
    photo_bytes, mime = await _read_photo(photo, explain.settings.max_photo_mb)
    if not title and not photo_bytes:
        raise api_error(422, "need_text_or_photo")
    try:
        topic = await explain.start(
            session,
            user.id,
            title or t("photo_title", user.lang),
            photo=photo_bytes,
            photo_mime=mime,
            subject=subject,
            grade=grade,
            source="web",
            lang=user.lang,
        )
    except ExplainError as exc:
        _raise(exc)
    finally:
        del photo_bytes
    return topic_public(topic)


@router.get("/{topic_id}")
async def get_explain_topic(
    topic_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    explain: ExplainService = Depends(get_explain),
):
    try:
        topic = await explain.get_owned(session, user.id, topic_id)
    except ExplainError as exc:
        _raise(exc)
    return topic_public(topic)


@router.post("/{topic_id}/answer")
async def answer_step(
    topic_id: int,
    body: AnswerIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    explain: ExplainService = Depends(get_explain),
):
    try:
        result = await explain.answer(session, user.id, topic_id, body.step, body.option)
    except ExplainError as exc:
        _raise(exc)
    return {
        "correct": result.correct,
        "points_awarded": result.points_awarded,
        "attempts": result.attempts,
        "completed": result.completed,
        "total_points": result.total_points,
        "level": level_for(result.total_points),
        "streak": result.streak,
        "topic": topic_public(result.topic),
    }


@router.post("/{topic_id}/simplify")
async def simplify_step(
    topic_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    explain: ExplainService = Depends(get_explain),
):
    try:
        simpler = await explain.simplify(session, user.id, topic_id, lang=user.lang)
    except ExplainError as exc:
        _raise(exc)
    return {"simpler": simpler}


@router.post("/{topic_id}/practice")
async def practice(
    topic_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    explain: ExplainService = Depends(get_explain),
):
    try:
        tasks = await explain.practice(session, user.id, topic_id, lang=user.lang)
    except ExplainError as exc:
        _raise(exc)
    return {"tasks": tasks}


@router.post("/{topic_id}/report")
async def report_mistake(
    topic_id: int,
    body: ReportIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    explain: ExplainService = Depends(get_explain),
):
    """«⚠️ Здесь ошибка» — жалоба уходит учителю и владельцу бота."""
    try:
        created = await explain.report(
            session, user.id, topic_id, body.step, kind=body.kind, comment=body.comment
        )
    except ExplainError as exc:
        _raise(exc)
    return {"ok": True, "already_reported": not created}
