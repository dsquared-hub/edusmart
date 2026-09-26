"""Квесты Paper-to-Digital: задача по пройденной теме → фото решения из тетради → EduCoin ×2."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import api_error, current_user, get_explain, get_session, get_work_checker
from app.api.routers.explain import _read_photo
from app.api.routers.stories import current_student
from app.db.models import Student, User
from app.services import paper_quests
from app.services.explain import ExplainError, ExplainService

router = APIRouter(prefix="/api/quests", tags=["quests"])


class CreateIn(BaseModel):
    topic_id: int


@router.get("")
async def list_quests(student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)):
    return {
        "quests": [paper_quests.public(q) for q in await paper_quests.recent(session, student.user_id)],
        "reward": paper_quests.QUEST_COINS,
        "per_day": paper_quests.PAPER_QUESTS_PER_DAY,
    }


@router.post("")
async def create_quest(
    body: CreateIn,
    user: User = Depends(current_user),
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
    explain: ExplainService = Depends(get_explain),
):
    try:
        quest = await paper_quests.create(session, explain, user, body.topic_id)
    except ExplainError as exc:
        raise api_error(exc.status, exc.code)
    except paper_quests.QuestError as exc:
        raise api_error(exc.status, exc.code)
    return paper_quests.public(quest)


@router.get("/{quest_id}")
async def get_quest(quest_id: int, student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)):
    try:
        return paper_quests.public(await paper_quests.get_owned(session, student.user_id, quest_id))
    except paper_quests.QuestError as exc:
        raise api_error(exc.status, exc.code)


@router.post("/{quest_id}/photo")
async def check_quest_photo(
    quest_id: int,
    photo: UploadFile = File(...),
    user: User = Depends(current_user),
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
    explain: ExplainService = Depends(get_explain),
    checker=Depends(get_work_checker),
):
    data, mime = await _read_photo(photo, explain.settings.max_photo_mb)
    if not data:
        raise api_error(422, "need_photo")
    try:
        return await paper_quests.check_photo(session, checker, student, user, quest_id, data, mime)
    except paper_quests.QuestError as exc:
        raise api_error(exc.status, exc.code)
    finally:
        del data
