"""Кабинет родителя / учителя на сайте — та же сводка, что в боте."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import api_error, current_user, get_session
from app.db.models import User
from app.services.cabinet import parent_cabinet, teacher_cabinet

router = APIRouter(prefix="/api", tags=["cabinet"])


@router.get("/cabinet")
async def get_cabinet(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    if user.role == "parent":
        cards = await parent_cabinet(session, user)
        return {
            "role": "parent",
            "children": [
                {
                    "id": c.summary.id,
                    "name": c.summary.name,
                    "grade": c.summary.grade,
                    "points": c.summary.points,
                    "streak": c.summary.streak,
                    "last_active_on": c.summary.last_active_on.isoformat() if c.summary.last_active_on else None,
                    "topics_completed": c.summary.topics_completed,
                    "topics_week": c.summary.topics_week,
                    "accuracy": c.summary.accuracy,
                    "evening": None
                    if c.evening is None
                    else {"status": c.evening.status, "score": c.evening.score, "total": c.evening.total},
                    "week": c.week,
                    "readiness": [{"subject": name, "score": score} for name, score in c.readiness],
                }
                for c in cards
            ],
        }
    if user.role == "teacher":
        summary = await teacher_cabinet(session, user)
        return {
            "role": "teacher",
            "class": {
                "students": summary.students,
                "active_today": summary.active_today,
                "topics_week": summary.topics_week,
                "accuracy": summary.accuracy,
                "checks_to_review": summary.checks_to_review,
                "weak": [{"title": title, "mistakes": n} for title, n in summary.weak],
            },
        }
    raise api_error(403, "forbidden")
