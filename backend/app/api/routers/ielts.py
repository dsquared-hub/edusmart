"""IELTS AI Coach: обзор секций, Writing (Task 1 / Task 2) — черновик, сдача, оценка."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import api_error, get_explain, get_session
from app.api.routers.stories import current_student
from app.db.models import Student
from app.services import ielts
from app.services.explain import ExplainError, ExplainService

router = APIRouter(prefix="/api/ielts", tags=["ielts"])


class WritingIn(BaseModel):
    task: int = Field(ge=1, le=2)


class TestIn(BaseModel):
    kind: str


class AnswersIn(BaseModel):
    answers: dict[str, int | str | None]


class TextIn(BaseModel):
    text: str = Field(max_length=ielts.MAX_ESSAY_CHARS * 2)


def _raise(exc: Exception):
    if isinstance(exc, (ielts.IeltsError, ExplainError)):
        raise api_error(exc.status, exc.code)
    raise exc


@router.get("")
async def overview(student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)):
    attempts = await ielts.recent(session, student.user_id)
    return {
        "grade": student.grade,
        "min_grade": ielts.MIN_GRADE,
        "attempts": [ielts.brief(a) for a in attempts],
        **ielts.overview(attempts),
        "writing": {str(k): {"minutes": v["minutes"], "min_words": v["min_words"]} for k, v in ielts.WRITING.items()},
    }


@router.post("/writing")
async def start_writing(
    body: WritingIn,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
    explain: ExplainService = Depends(get_explain),
):
    try:
        attempt = await ielts.start_writing(session, explain, student, body.task)
        _, material = await ielts.get_owned(session, student.user_id, attempt.id)
    except (ielts.IeltsError, ExplainError) as exc:
        _raise(exc)
    return ielts.public(attempt, material)


@router.get("/attempts/{attempt_id}")
async def get_attempt(attempt_id: int, student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)):
    try:
        attempt, material = await ielts.get_owned(session, student.user_id, attempt_id)
    except ielts.IeltsError as exc:
        _raise(exc)
    return ielts.public(attempt, material)


@router.put("/attempts/{attempt_id}/draft")
async def save_draft(
    attempt_id: int, body: TextIn, student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)
):
    try:
        await ielts.save_draft(session, student.user_id, attempt_id, body.text)
    except ielts.IeltsError as exc:
        _raise(exc)
    return {"ok": True}


@router.post("/attempts/{attempt_id}/submit")
async def submit_writing(
    attempt_id: int,
    body: TextIn,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
    explain: ExplainService = Depends(get_explain),
):
    try:
        attempt = await ielts.submit_writing(session, explain, student, attempt_id, body.text)
        _, material = await ielts.get_owned(session, student.user_id, attempt.id)
    except (ielts.IeltsError, ExplainError) as exc:
        _raise(exc)
    return ielts.public(attempt, material)


@router.post("/tests")
async def start_test(
    body: TestIn,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
    explain: ExplainService = Depends(get_explain),
):
    """Reading или Listening: тест с мгновенной проверкой."""
    try:
        attempt = await ielts.start_test(session, explain, student, body.kind)
        _, material = await ielts.get_owned(session, student.user_id, attempt.id)
    except (ielts.IeltsError, ExplainError) as exc:
        _raise(exc)
    return ielts.public(attempt, material)


@router.post("/attempts/{attempt_id}/answers")
async def submit_test(
    attempt_id: int, body: AnswersIn, student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)
):
    try:
        attempt = await ielts.submit_test(session, student, attempt_id, body.answers)
        _, material = await ielts.get_owned(session, student.user_id, attempt.id)
    except ielts.IeltsError as exc:
        _raise(exc)
    return ielts.public(attempt, material)


@router.post("/speaking")
async def start_speaking(
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
    explain: ExplainService = Depends(get_explain),
):
    try:
        attempt = await ielts.start_speaking(session, explain, student)
        _, material = await ielts.get_owned(session, student.user_id, attempt.id)
    except (ielts.IeltsError, ExplainError) as exc:
        _raise(exc)
    return ielts.public(attempt, material)


@router.post("/attempts/{attempt_id}/speak")
async def speak(
    attempt_id: int,
    turn: int = Form(...),
    audio: UploadFile = File(...),
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
    explain: ExplainService = Depends(get_explain),
):
    """Ответ ученика голосом. Аудио живёт только в памяти этого запроса."""
    mime = (audio.content_type or "").split(";")[0]
    if mime not in ielts.AUDIO_MIME:
        raise api_error(415, "bad_audio_type")
    data = await audio.read(ielts.MAX_AUDIO_BYTES + 1)
    await audio.close()
    if len(data) > ielts.MAX_AUDIO_BYTES:
        raise api_error(413, "audio_too_large")
    try:
        attempt = await ielts.speak(session, explain, student, attempt_id, turn, data, mime)
        _, material = await ielts.get_owned(session, student.user_id, attempt.id)
    except ielts.IeltsError as exc:
        _raise(exc)
    finally:
        del data
    return ielts.public(attempt, material)


@router.post("/attempts/{attempt_id}/grade")
async def grade_speaking(
    attempt_id: int,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
    explain: ExplainService = Depends(get_explain),
):
    try:
        attempt = await ielts.grade_speaking(session, explain, student, attempt_id)
        _, material = await ielts.get_owned(session, student.user_id, attempt.id)
    except ielts.IeltsError as exc:
        _raise(exc)
    return ielts.public(attempt, material)
