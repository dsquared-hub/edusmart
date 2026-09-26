"""Stories ученика: лента, свои Stories по теме, ответы на мини-вопросы и EduCoin.
Учитель отправляет Stories из материалов урока — POST /api/teacher/materials/{id}/stories."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import api_error, current_user, get_explain, get_session
from app.db.models import Student, StoryDeck, StoryView, User
from app.repositories.students import get_student
from app.services import stories
from app.services.explain import ExplainError, ExplainService
from app.services.gemini import SUBJECTS

router = APIRouter(prefix="/api/stories", tags=["stories"])


async def current_student(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> Student:
    student = await get_student(session, user.id) if user.role == "student" else None
    if student is None:
        raise api_error(403, "not_student")
    return student


class CreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    subject: str | None = None
    grade: int | None = Field(None, ge=5, le=11)


class AnswerIn(BaseModel):
    slide: int = Field(ge=0)
    option: int = Field(ge=0)


def _utc(value) -> str | None:
    return value.isoformat() + "Z" if value else None


def _brief(view: StoryView, deck: StoryDeck, author: User) -> dict:
    return {
        "id": view.id,
        "title": deck.title,
        "subject": deck.subject,
        "emoji": next((s.get("emoji") for s in deck.slides if s.get("emoji")), "") or "📖",
        "slides": len(deck.slides),
        "status": view.status,
        "coins": view.coins,
        "from_teacher": author.display_name if author.role == "teacher" else None,
        "created_at": _utc(view.created_at),
    }


def _full(view: StoryView, deck: StoryDeck, author: User) -> dict:
    return {**_brief(view, deck, author), "cards": stories.public_slides(view, deck)}


@router.get("")
async def list_stories(student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)):
    return {
        "stories": [_brief(v, d, a) for v, d, a in await stories.feed(session, student.user_id)],
        "coins": student.coins or 0,
        "reward": {"story": stories.COINS_FOR_STORY, "answer": stories.COINS_PER_ANSWER},
    }


@router.post("")
async def create_story(
    body: CreateIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    explain: ExplainService = Depends(get_explain),
):
    if user.role != "student":
        raise api_error(403, "not_student")
    if body.subject is not None and body.subject not in SUBJECTS:
        raise api_error(422, "bad_subject")
    try:
        view = await stories.create_own(session, explain, user, body.title, subject=body.subject, grade=body.grade)
    except ExplainError as exc:
        raise api_error(exc.status, exc.code)
    except stories.StoryError as exc:
        raise api_error(exc.status, exc.code)
    view, deck = await stories.get_owned(session, user.id, view.id)
    return _full(view, deck, user)


@router.get("/{view_id}")
async def get_story(view_id: int, student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)):
    try:
        view, deck = await stories.get_owned(session, student.user_id, view_id)
    except stories.StoryError as exc:
        raise api_error(exc.status, exc.code)
    return _full(view, deck, await session.get(User, deck.author_user_id))


@router.post("/{view_id}/answer")
async def answer_story(
    view_id: int, body: AnswerIn, student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)
):
    try:
        return await stories.answer(session, student.user_id, view_id, body.slide, body.option)
    except stories.StoryError as exc:
        raise api_error(exc.status, exc.code)


@router.post("/{view_id}/complete")
async def complete_story(view_id: int, student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)):
    try:
        return await stories.complete(session, student, view_id)
    except stories.StoryError as exc:
        raise api_error(exc.status, exc.code)

