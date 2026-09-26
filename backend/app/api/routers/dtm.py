"""ДТМ-симулятор: вариант из 90 вопросов на 180 минут, ответы, итог по блокам и разбор."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import api_error, current_user, get_session
from app.api.routers.family import get_question_generator
from app.api.routers.stories import current_student
from app.db.models import Student, User
from app.services import dtm
from app.services.questions import QuestionGenerator

router = APIRouter(prefix="/api/dtm", tags=["dtm"])


def _lang(user: User) -> str:
    return user.lang if user.lang in ("ru", "uz", "en") else "ru"


class StartIn(BaseModel):
    spec1: str
    spec2: str


class AnswerIn(BaseModel):
    slot: int
    option: int | None = None  # None — снять ответ


@router.get("")
async def overview(
    user: User = Depends(current_user), student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)
):
    return {
        "subjects": dtm.subjects_view(_lang(user)),
        "grade": student.grade,
        "tests": [dtm.brief(t, _lang(user)) for t in await dtm.recent(session, student.user_id)],
    }


@router.post("")
async def start_test(
    body: StartIn,
    user: User = Depends(current_user),
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
    generator: QuestionGenerator = Depends(get_question_generator),
):
    # Вопросы — на языке профиля; английский интерфейс — русские вопросы (ДТМ сдают на узбекском или русском)
    lang = "uz" if user.lang == "uz" else "ru"
    try:
        test = await dtm.start(session, generator, student, lang, body.spec1, body.spec2)
    except dtm.DtmError as exc:
        raise api_error(exc.status, exc.code)
    return await dtm.public(session, test, _lang(user))


@router.get("/{test_id}")
async def get_test(
    test_id: int, user: User = Depends(current_user), student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)
):
    try:
        test = await dtm.get_owned(session, student.user_id, test_id)
    except dtm.DtmError as exc:
        raise api_error(exc.status, exc.code)
    return await dtm.public(session, test, _lang(user))


@router.put("/{test_id}/answer")
async def answer(test_id: int, body: AnswerIn, student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)):
    try:
        test = await dtm.answer(session, student.user_id, test_id, body.slot, body.option)
    except dtm.DtmError as exc:
        raise api_error(exc.status, exc.code)
    return {"answered": sum(s["answer"] is not None for s in test.slots)}


@router.post("/{test_id}/finish")
async def finish_test(
    test_id: int, user: User = Depends(current_user), student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)
):
    try:
        test = await dtm.finish(session, await dtm.get_owned(session, student.user_id, test_id))
    except dtm.DtmError as exc:
        raise api_error(exc.status, exc.code)
    return await dtm.public(session, test, _lang(user))
