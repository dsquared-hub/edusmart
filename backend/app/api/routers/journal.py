"""Журнал результатов учеников — для родителя и учителя."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import api_error, current_user, get_session
from app.db.models import User
from app.services.journal import MAX_PAGE_SIZE, PAGE_SIZE, JournalError, build_journal

router = APIRouter(prefix="/api", tags=["journal"])


def _utc_iso(value: datetime | None) -> str | None:
    # В БД наивное UTC — отдаём с явной зоной, чтобы браузер показал местное время
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


@router.get("/journal")
async def get_journal(
    student_id: int | None = None,
    before: int | None = Query(None, description="id последней показанной темы — «показать ещё»"),
    limit: int = Query(PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        journal = await build_journal(
            session, user, student_id=student_id, limit=limit, before_id=before
        )
    except JournalError as exc:
        raise api_error(exc.status, exc.code)
    return {
        "students": [
            {
                "id": s.id,
                "name": s.name,
                "grade": s.grade,
                "points": s.points,
                "streak": s.streak,
                "last_active_on": s.last_active_on.isoformat() if s.last_active_on else None,
                "topics_completed": s.topics_completed,
                "topics_week": s.topics_week,
                "accuracy": s.accuracy,
                "weak": [{"title": title, "mistakes": count} for title, count in s.weak],
            }
            for s in journal.students
        ],
        "entries": [
            {
                "topic_id": e.topic_id,
                "student_id": e.student_id,
                "student_name": e.student_name,
                "title": e.title,
                "subject": e.subject,
                "source": e.source,
                "completed_at": _utc_iso(e.completed_at),
                "questions": e.questions,
                "first_try": e.first_try,
                "mistakes": e.mistakes,
                "points": e.points,
            }
            for e in journal.entries
        ],
        "has_more": journal.has_more,
    }
