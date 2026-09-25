"""API Academic Copilot (Модуль 5.1): ИИ-проверка рукописных работ учителем."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_session
from app.core.config import get_settings
from app.db.models import User, WorkCheck, WorkCheckItem
from app.services import media
from app.services import work_checks as svc
from app.services.gemini import SUBJECTS

router = APIRouter(prefix="/api/v1/teacher/checks", tags=["teacher-checks"])


def _raise(exc: svc.CheckError):
    raise HTTPException(exc.status, detail={"code": exc.code, **exc.extra})


def _iso(value: datetime | None) -> str | None:
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def _item(item: WorkCheckItem, full: bool = False) -> dict:
    settings = get_settings()
    data = {
        "id": item.id,
        "student_id": item.student_user_id,
        "file_name": item.file_name,
        "mime": item.mime,
        "status": item.status,
        "ai_score": item.ai_score,
        "teacher_score": item.teacher_score,
        "final_score": item.final_score,
        "confidence": item.confidence,
        "neatness": item.neatness,
        "level": None if item.status in svc.ACTIVE else svc.review_level(item, settings),
        "blocker": None if item.confirmed_at else svc.confirm_blocker(item, settings),
        "viewed": item.viewed_at is not None,
        "confirmed_at": _iso(item.confirmed_at),
        "error": item.error if item.status == "failed" else None,
    }
    if full:
        data.update(
            recognized_text=item.recognized_text,
            ai_comment=item.ai_comment,
            ai_marks=item.ai_marks or [],
            teacher_comment=item.teacher_comment,
            teacher_marks=item.teacher_marks,
        )
    return data


def _check(check: WorkCheck, counts: dict | None = None) -> dict:
    return {
        "id": check.id,
        "title": check.title,
        "subject": check.subject,
        "grade": check.grade,
        "task_text": check.task_text,
        "answer_key": check.answer_key,
        "max_score": check.max_score,
        "training_consent": check.training_consent,
        "status": check.status,
        "created_at": _iso(check.created_at),
        "confirmed_at": _iso(check.confirmed_at),
        **({"counts": counts} if counts is not None else {}),
    }


@router.post("")
async def upload_checks(
    files: list[UploadFile] = File(...),
    title: str = Form(..., min_length=1, max_length=255),
    subject: str | None = Form(None),
    grade: int | None = Form(None, ge=1, le=11),
    task_text: str | None = Form(None, max_length=4000),
    answer_key: str | None = Form(None, max_length=4000),
    max_score: int = Form(5, ge=1, le=100),
    training_consent: bool = Form(False),
    # Ученик для каждого файла по порядку; 0 или пусто — не указан
    student_ids: list[int] | None = Form(None),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    settings = get_settings()
    if subject is not None and subject not in SUBJECTS:
        raise HTTPException(422, detail={"code": "bad_subject"})
    if len(files) > settings.check_max_files:
        raise HTTPException(413, detail={"code": "too_many_files", "limit": settings.check_max_files})
    limit = settings.check_max_file_mb * 1024 * 1024
    incoming: list[svc.IncomingFile] = []
    for i, upload in enumerate(files):
        data = await upload.read(limit + 1)
        await upload.close()
        if len(data) > limit:
            raise HTTPException(413, detail={"code": "file_too_large", "file": upload.filename, "limit_mb": settings.check_max_file_mb})
        student = student_ids[i] if student_ids and i < len(student_ids) and student_ids[i] else None
        incoming.append(svc.IncomingFile(name=upload.filename or f"work-{i + 1}", data=data, student_id=student))
    try:
        check = await svc.create_check(
            session,
            user,
            title=title,
            files=incoming,
            subject=subject,
            grade=grade,
            task_text=task_text,
            answer_key=answer_key,
            max_score=max_score,
            training_consent=training_consent,
            settings=settings,
        )
    except svc.CheckError as exc:
        _raise(exc)
    return {"check_id": check.id, "status": check.status, "items": len(incoming)}


@router.get("")
async def list_checks(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    if user.role != "teacher":
        raise HTTPException(403, detail={"code": "not_teacher"})
    return {"checks": [_check(c, counts) for c, counts in await svc.list_checks(session, user)]}


@router.get("/{check_id}")
async def get_check(
    check_id: int,
    level: Literal["one_click", "review", "manual"] | None = None,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    """Статус и результаты. level — фильтр очереди по уверенности ИИ."""
    try:
        check = await svc.get_check(session, user, check_id)
    except svc.CheckError as exc:
        _raise(exc)
    items = [_item(i) for i in await svc.check_items(session, check.id)]
    if level:
        items = [i for i in items if i["level"] == level]
    return {**_check(check), "items": items}


@router.get("/{check_id}/items/{item_id}")
async def get_item(check_id: int, item_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    """Открыть работу. Открытие фиксируется: после него «Проверьте» можно подтверждать."""
    try:
        _, item = await svc.get_item(session, user, check_id, item_id, mark_viewed=True)
    except svc.CheckError as exc:
        _raise(exc)
    return _item(item, full=True)


@router.get("/{check_id}/items/{item_id}/file")
async def get_item_file(check_id: int, item_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    try:
        _, item = await svc.get_item(session, user, check_id, item_id)
        data = media.load(item.storage_key)
    except svc.CheckError as exc:
        _raise(exc)
    except (media.MediaError, FileNotFoundError):
        raise HTTPException(404, detail={"code": "file_not_found"})
    # Фото детских работ: не кэшировать на общих прокси
    return Response(data, media_type=item.mime, headers={"Cache-Control": "private, max-age=600"})


class ItemPatch(BaseModel):
    score: int | None = Field(None, ge=0, le=100)
    comment: str | None = Field(None, max_length=2000)
    marks: list[dict] | None = None
    student_id: int | None = None


@router.patch("/{check_id}/items/{item_id}")
async def patch_item(
    check_id: int, item_id: int, body: ItemPatch, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    try:
        item = await svc.update_item(session, user, check_id, item_id, **body.model_dump(exclude_unset=True))
    except svc.CheckError as exc:
        _raise(exc)
    return _item(item, full=True)


class ConfirmIn(BaseModel):
    item_ids: list[int] | None = None  # не указано — все неподтверждённые


@router.post("/{check_id}/confirm")
async def confirm_check(
    check_id: int, body: ConfirmIn | None = None, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    try:
        check = await svc.confirm(session, user, check_id, body.item_ids if body else None)
    except svc.CheckError as exc:
        _raise(exc)
    items = [_item(i) for i in await svc.check_items(session, check.id)]
    return {**_check(check), "items": items}
