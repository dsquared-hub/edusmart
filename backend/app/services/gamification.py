"""Геймификация: очки, уровни, серии дней."""
from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Student
from app.repositories.students import mark_activity_day

POINTS_PER_LEVEL = 100


def level_for(points: int) -> int:
    """Каждые 100 очков — новый уровень, старт с уровня 1."""
    return points // POINTS_PER_LEVEL + 1


def points_to_next_level(points: int) -> int:
    return POINTS_PER_LEVEL - (points % POINTS_PER_LEVEL)


def level_progress(points: int) -> float:
    """Доля пути до следующего уровня, 0..1 — для полоски прогресса."""
    return (points % POINTS_PER_LEVEL) / POINTS_PER_LEVEL


def add_points(student: Student, points: int) -> None:
    student.points = (student.points or 0) + points


def iso_week(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def freezes_left(student: Student, today: date, per_week: int) -> int:
    """Сколько бесплатных «заморозок» серии осталось на этой неделе."""
    used = student.freezes_used if student.freeze_week == iso_week(today) else 0
    return max(0, per_week - (used or 0))


async def mark_active(session: AsyncSession, student: Student, today: date, freezes_per_week: int | None = None) -> None:
    """Обновляет серию дней подряд и логирует день активности.

    Пропуск не сбрасывает серию, пока хватает бесплатных «заморозок» (2 в неделю):
    каждый пропущенный день тратит одну. Серия не давит на ребёнка.
    """
    await mark_activity_day(session, student.user_id, today)
    if student.last_active_on == today:
        return
    missed = (today - student.last_active_on).days - 1 if student.last_active_on else None
    if freezes_per_week is None:
        from app.core.config import get_settings

        freezes_per_week = get_settings().freezes_per_week
    if missed == 0:
        student.streak = (student.streak or 0) + 1
    elif missed is not None and 0 < missed <= freezes_left(student, today, freezes_per_week):
        week = iso_week(today)
        student.freezes_used = (student.freezes_used if student.freeze_week == week else 0) + missed
        student.freeze_week = week
        student.streak = (student.streak or 0) + 1
    else:
        student.streak = 1
    student.last_active_on = today
