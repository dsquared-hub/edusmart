"""PvP-дуэли: вызов (по коду или открытый), игра по одному вопросу с серверным таймером, итог."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import api_error, current_user, get_explain, get_session
from app.api.routers.family import get_question_generator
from app.api.routers.stories import current_student
from app.db.models import Duel, Student, User
from app.services import duels
from app.services.explain import ExplainError, ExplainService
from app.services.questions import QuestionGenerator

router = APIRouter(prefix="/api/duels", tags=["duels"])


class CreateIn(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    subject: str | None = None
    public: bool = False


class JoinIn(BaseModel):
    code: str = Field(min_length=4, max_length=8)


class AnswerIn(BaseModel):
    n: int = Field(ge=0)
    option: int = Field(ge=0)


async def _names(session: AsyncSession, duel_list: list[Duel]) -> dict[int, str]:
    ids = {p for d in duel_list for p in (d.creator_id, d.opponent_id) if p}
    users = await session.scalars(select(User).where(User.id.in_(ids))) if ids else []
    # Сопернику — только имя (без фамилии): дуэль видят ученики из разных семей
    return {u.id: (u.full_name or "").split(" ")[0] or "—" for u in users}


async def _view(session: AsyncSession, duel: Duel, me: int) -> dict:
    return duels.public_view(duel, me, await _names(session, [duel]))


def _raise(exc: Exception):
    if isinstance(exc, (duels.DuelError, ExplainError)):
        raise api_error(exc.status, exc.code)
    raise exc


@router.get("")
async def list_duels(student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)):
    items = await duels.mine(session, student.user_id)
    names = await _names(session, items)
    return {"duels": [duels.public_view(d, student.user_id, names) for d in items], "coins": student.coins or 0}


@router.post("")
async def create_duel(
    body: CreateIn,
    user: User = Depends(current_user),
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
    explain: ExplainService = Depends(get_explain),
    generator: QuestionGenerator = Depends(get_question_generator),
):
    try:
        duel = await duels.create(session, explain, generator, user, student, body.topic, body.subject, body.public)
    except (duels.DuelError, ExplainError) as exc:
        _raise(exc)
    return await _view(session, duel, student.user_id)


@router.post("/join")
async def join_duel(body: JoinIn, student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)):
    try:
        duel = await duels.join(session, student, body.code)
    except duels.DuelError as exc:
        _raise(exc)
    return await _view(session, duel, student.user_id)


@router.post("/random")
async def random_duel(student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)):
    try:
        duel = await duels.random_opponent(session, student)
    except duels.DuelError as exc:
        _raise(exc)
    return await _view(session, duel, student.user_id)


@router.get("/{duel_id}")
async def get_duel(duel_id: int, student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)):
    try:
        duel = await duels.get_for(session, student.user_id, duel_id)
    except duels.DuelError as exc:
        _raise(exc)
    return await _view(session, duel, student.user_id)


@router.post("/{duel_id}/next")
async def next_question(duel_id: int, student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)):
    try:
        return {"question": await duels.next_question(session, student.user_id, duel_id)}
    except duels.DuelError as exc:
        _raise(exc)


@router.post("/{duel_id}/answer")
async def answer(duel_id: int, body: AnswerIn, student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)):
    try:
        return await duels.answer(session, student, duel_id, body.n, body.option)
    except duels.DuelError as exc:
        _raise(exc)
