"""Exam Readiness Score (ТЗ, раздел 3): готовность к экзамену по предмету, 0–100.

    ERS = 0.50·M + 0.25·S + 0.15·V + 0.10·R   (веса — ERS_WEIGHTS в .env)

M — доля тем предмета, освоенных на 80%+ по последним попыткам;
S — средний результат повторных вопросов через 3, 7 и 14 дней;
V — время решения относительно медианы класса (не больше 100%);
R — доля дней с занятиями за последние 30 дней.
Меньше ERS_MIN_ATTEMPTS ответов по предмету — «Недостаточно данных».
Пересчитывается после каждого теста; история хранится для графика.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.timeutil import local_today, utcnow
from app.db.models import ActivityDay, Attempt, CurriculumSubject, CurriculumTopic, ReadinessScore, Student, TeacherLink
from app.services.curriculum import subject_topics

LAST_N = 5  # освоение темы — по последним 5 ответам


def weights(settings: Settings) -> tuple[float, float, float, float]:
    parts = [float(x) for x in settings.ers_weights.split(",")]
    if len(parts) != 4 or abs(sum(parts) - 1.0) > 0.01:
        raise ValueError("ERS_WEIGHTS: нужно 4 веса с суммой 1.0")
    return tuple(parts)  # type: ignore[return-value]


@dataclass
class TopicMastery:
    topic: CurriculumTopic
    accuracy: float | None  # None — ответов по теме ещё не было
    attempts: int


async def topic_mastery(session: AsyncSession, student_id: int, topics: list[CurriculumTopic]) -> list[TopicMastery]:
    out = []
    for topic in topics:
        rows = list(
            await session.scalars(
                select(Attempt.is_correct)
                .where(Attempt.student_id == student_id, Attempt.topic_id == topic.id)
                .order_by(desc(Attempt.created_at), desc(Attempt.id))
                .limit(LAST_N)
            )
        )
        out.append(TopicMastery(topic, sum(rows) / len(rows) if rows else None, len(rows)))
    return out


async def _peer_ids(session: AsyncSession, student: Student) -> list[int]:
    """Класс: ученики тех же учителей; нет учителя — ученики того же класса."""
    teachers = select(TeacherLink.teacher_user_id).where(TeacherLink.student_user_id == student.user_id)
    peers = list(
        await session.scalars(
            select(TeacherLink.student_user_id).where(TeacherLink.teacher_user_id.in_(teachers)).distinct()
        )
    )
    if len(peers) <= 1 and student.grade:
        peers = list(await session.scalars(select(Student.user_id).where(Student.grade == student.grade)))
    return [p for p in peers if p != student.user_id]


async def _median_time(session: AsyncSession, student_id: int, topic_ids: list[int]) -> float | None:
    times = list(
        await session.scalars(
            select(Attempt.time_ms).where(
                Attempt.student_id == student_id, Attempt.topic_id.in_(topic_ids), Attempt.is_correct, Attempt.time_ms > 0
            )
        )
    )
    return statistics.median(times) if times else None


async def compute(
    session: AsyncSession, student_id: int, subject_id: int, settings: Settings | None = None
) -> ReadinessScore:
    settings = settings or get_settings()
    wm, ws, wv, wr = weights(settings)
    student = await session.get(Student, student_id)
    topics = await subject_topics(session, subject_id)
    topic_ids = [t.id for t in topics]
    total = await session.scalar(
        select(func.count(Attempt.id)).where(Attempt.student_id == student_id, Attempt.topic_id.in_(topic_ids))
    ) or 0
    mastery = await topic_mastery(session, student_id, topics)
    # Совет: сначала самые слабые из пройденных тем, потом ещё не начатые
    not_mastered = [m for m in mastery if m.accuracy is None or m.accuracy < settings.ers_mastery_threshold]
    not_mastered.sort(key=lambda m: (m.accuracy is None, m.accuracy if m.accuracy is not None else 0, m.topic.order))
    advice = [m.topic.id for m in not_mastered[:3]]

    if total < settings.ers_min_attempts or not topics:
        row = ReadinessScore(
            student_id=student_id, subject_id=subject_id, score=None,
            components={"attempts": total, "min_attempts": settings.ers_min_attempts, "advice": advice},
        )
        session.add(row)
        await session.flush()
        return row

    m = sum(1 for x in mastery if x.accuracy is not None and x.accuracy >= settings.ers_mastery_threshold) / len(topics)

    reviews = list(
        await session.scalars(
            select(Attempt.is_correct).where(
                Attempt.student_id == student_id, Attempt.topic_id.in_(topic_ids), Attempt.is_review,
                Attempt.created_at >= utcnow() - timedelta(days=60),
            )
        )
    )
    s_estimated = not reviews
    s = sum(reviews) / len(reviews) if reviews else m  # повторений ещё не было — нейтрально, как M

    own = await _median_time(session, student_id, topic_ids)
    peer_medians = [t for p in await _peer_ids(session, student) if (t := await _median_time(session, p, topic_ids))]
    v_estimated = own is None or not peer_medians
    v = 1.0 if v_estimated else min(1.0, statistics.median(peer_medians) / own)

    today = local_today()
    active = await session.scalar(
        select(func.count(ActivityDay.id)).where(
            ActivityDay.user_id == student_id, ActivityDay.date > today - timedelta(days=30), ActivityDay.date <= today
        )
    ) or 0
    r = min(1.0, active / 30)

    score = round(100 * (wm * m + ws * s + wv * v + wr * r))
    row = ReadinessScore(
        student_id=student_id,
        subject_id=subject_id,
        score=max(0, min(100, score)),
        components={
            "M": round(m, 3), "S": round(s, 3), "V": round(v, 3), "R": round(r, 3),
            "weights": [wm, ws, wv, wr], "attempts": total, "advice": advice,
            "S_estimated": s_estimated, "V_estimated": v_estimated,
        },
    )
    session.add(row)
    await session.flush()
    return row


async def latest(session: AsyncSession, student_id: int) -> list[tuple[CurriculumSubject, ReadinessScore]]:
    """Последний ERS по каждому предмету ученика."""
    subquery = (
        select(ReadinessScore.subject_id, func.max(ReadinessScore.id).label("last_id"))
        .where(ReadinessScore.student_id == student_id)
        .group_by(ReadinessScore.subject_id)
        .subquery()
    )
    rows = await session.execute(
        select(CurriculumSubject, ReadinessScore)
        .join(ReadinessScore, ReadinessScore.subject_id == CurriculumSubject.id)
        .join(subquery, subquery.c.last_id == ReadinessScore.id)
        .order_by(CurriculumSubject.grade, CurriculumSubject.code)
    )
    return [(s, r) for s, r in rows.all()]


async def history(session: AsyncSession, student_id: int, subject_id: int, limit: int = 60) -> list[ReadinessScore]:
    rows = await session.scalars(
        select(ReadinessScore)
        .where(ReadinessScore.student_id == student_id, ReadinessScore.subject_id == subject_id)
        .order_by(desc(ReadinessScore.calculated_at), desc(ReadinessScore.id))
        .limit(limit)
    )
    return list(reversed(list(rows)))
