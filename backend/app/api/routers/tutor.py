"""Сократовский тьютор на сайте: новый диалог (текст или фото задачи), ходы ученика."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import api_error, current_user, get_explain, get_session
from app.api.routers.explain import _read_photo
from app.api.routers.stories import current_student
from app.db.models import Student, User
from app.services import tutor
from app.services.explain import ExplainError, ExplainService
from app.services.gemini import SUBJECTS

router = APIRouter(prefix="/api/tutor", tags=["tutor"])


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=tutor.MAX_MESSAGE)


@router.get("")
async def list_dialogs(student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)):
    return {
        "dialogs": [
            {"id": d.id, "title": d.title, "subject": d.subject, "status": d.status, "points": d.points,
             "updated_at": d.updated_at.isoformat() + "Z" if d.updated_at else None}
            for d in await tutor.recent(session, student.user_id)
        ]
    }


@router.post("")
async def start_dialog(
    text: str = Form(""),
    subject: str | None = Form(None),
    grade: int | None = Form(None, ge=5, le=11),
    photo: UploadFile | None = File(None),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    explain: ExplainService = Depends(get_explain),
):
    if user.role != "student":
        raise api_error(403, "not_student")
    if subject is not None and subject not in SUBJECTS:
        raise api_error(422, "bad_subject")
    photo_bytes, mime = await _read_photo(photo, explain.settings.max_photo_mb)
    try:
        dialog = await tutor.start(
            session, explain, user, text, photo=photo_bytes, photo_mime=mime, subject=subject, grade=grade
        )
    except ExplainError as exc:
        raise api_error(exc.status, exc.code)
    except tutor.TutorError as exc:
        raise api_error(exc.status, exc.code)
    finally:
        del photo_bytes
    return tutor.public(dialog)


@router.get("/{tutor_id}")
async def get_dialog(tutor_id: int, student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)):
    try:
        return tutor.public(await tutor.get_owned(session, student.user_id, tutor_id))
    except tutor.TutorError as exc:
        raise api_error(exc.status, exc.code)


@router.post("/{tutor_id}/message")
async def send_message(
    tutor_id: int,
    body: MessageIn,
    user: User = Depends(current_user),
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
    explain: ExplainService = Depends(get_explain),
):
    try:
        dialog = await tutor.reply(session, explain, student, user, tutor_id, body.text)
    except tutor.TutorError as exc:
        raise api_error(exc.status, exc.code)
    return tutor.public(dialog)
