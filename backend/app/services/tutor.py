"""Сократовский тьютор (Dev-Spec, блок 1): ИИ не даёт готовых ответов — ведёт ученика
2–3 наводящими вопросами, ответ ученик находит сам.

Каждая реплика репетитора проверяется вторым запросом (правило проекта): не выдан ли
ответ, нет ли ошибки, правильно ли отмечено «решено». Не прошла — генерируем заново;
снова нет — отдаём безопасную общую подсказку, но не ответ.

Новый диалог тратит одну попытку из дневного лимита объяснений; ходов в диалоге —
не больше TUTOR_MAX_TURNS. Решил сам — очки (как два шага объяснения) и день активности.
Фото задачи живёт только в памяти первого запроса.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import t
from app.core.timeutil import local_today, utcnow
from app.db.models import Student, TutorSession, User
from app.repositories import usage as usage_repo
from app.repositories.students import get_student
from app.services.explain import MAX_TITLE_LENGTH, ExplainService
from app.services.gamification import add_points, mark_active

log = logging.getLogger(__name__)

TUTOR_MAX_TURNS = 15  # реплик ученика в одном диалоге
CHECK_ATTEMPTS = 2
TURN_TIMEOUT = 45.0  # секунд на один запрос к модели
MAX_MESSAGE = 1000


class TutorError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


def _msg(role: str, text: str) -> dict:
    return {"role": role, "text": text, "at": utcnow().isoformat() + "Z"}


def _points(explain: ExplainService) -> int:
    return explain.settings.points_per_step * 2


async def _checked_turn(
    explain: ExplainService, problem: str, history: list[dict], lang: str, **first_turn
) -> dict:
    """Реплика репетитора, прошедшая проверку. Проверяющий недоступен — не блокируем ученика."""
    lesson = explain.lesson
    for attempt in range(1, CHECK_ATTEMPTS + 1):
        # Ученик ждёт в чате: зависший запрос к модели обрываем, а не держим минуту
        turn = await asyncio.wait_for(lesson.tutor_turn(problem, history, lang=lang, **first_turn), TURN_TIMEOUT)
        if not explain.settings.verify_explanations:
            return turn
        try:
            verdict = await asyncio.wait_for(
                lesson.tutor_check(turn.get("problem") or problem, history, turn), TURN_TIMEOUT
            )
        except Exception as exc:
            log.warning("Проверка тьютора недоступна: %s", exc)
            return {**turn, "solved": False}  # без проверки «решено» не засчитываем
        if verdict["ok"]:
            return turn
        log.warning("Реплика тьютора не прошла проверку (попытка %s): %s", attempt, verdict["issue"])
    # Безопасно: общая наводящая подсказка вместо реплики, которая могла выдать ответ
    return {**turn, "reply": t("tutor_safe_hint", lang), "solved": False}


async def start(
    session: AsyncSession,
    explain: ExplainService,
    user: User,
    text: str,
    *,
    photo: bytes | None = None,
    photo_mime: str | None = None,
    subject: str | None = None,
    grade: int | None = None,
) -> TutorSession:
    text = text.strip()
    if not text and not photo:
        raise TutorError("need_text_or_photo", 422)
    if len(text) > MAX_TITLE_LENGTH:
        raise TutorError("topic_too_long", 422)
    await explain.ensure_can_start(session, user.id)  # ученик, согласие, лимит
    today = local_today()
    if not await usage_repo.try_reserve(session, user.id, today, explain.settings.daily_explain_limit):
        raise TutorError("limit_reached", 429)
    await session.commit()

    history = [_msg("student", text or t("photo_title", user.lang))]
    try:
        turn = await _checked_turn(
            explain, text, history, user.lang, photo=photo, photo_mime=photo_mime, subject=subject, grade=grade
        )
    except Exception as exc:
        log.warning("Тьютор не ответил: %s", exc)
        await usage_repo.refund(session, user.id, today)
        await session.commit()
        raise TutorError("generation_failed", 502) from exc

    problem = turn.get("problem") or text
    tutor = TutorSession(
        student_id=user.id,
        title=(text or problem)[:255],
        problem=problem,
        subject=subject,
        grade=grade,
        messages=[*history, _msg("tutor", turn["reply"])],
    )
    session.add(tutor)
    await mark_active(session, await get_student(session, user.id), today)
    await session.commit()
    return tutor


async def get_owned(session: AsyncSession, student_id: int, tutor_id: int) -> TutorSession:
    tutor = await session.get(TutorSession, tutor_id)
    if tutor is None or tutor.student_id != student_id:
        raise TutorError("tutor_not_found", 404)
    return tutor


async def reply(
    session: AsyncSession, explain: ExplainService, student: Student, user: User, tutor_id: int, text: str
) -> TutorSession:
    tutor = await get_owned(session, student.user_id, tutor_id)
    text = text.strip()[:MAX_MESSAGE]
    if not text:
        raise TutorError("need_text", 422)
    if tutor.status == "solved":
        raise TutorError("tutor_solved", 409)
    if sum(m["role"] == "student" for m in tutor.messages) >= TUTOR_MAX_TURNS:
        raise TutorError("tutor_turns_limit", 429)
    history = [*tutor.messages, _msg("student", text)]
    try:
        turn = await _checked_turn(explain, tutor.problem, history, user.lang)
    except Exception as exc:
        log.warning("Тьютор не ответил: %s", exc)
        raise TutorError("generation_failed", 502) from exc

    tutor.messages = [*history, _msg("tutor", turn["reply"])]
    today = local_today()
    if turn["solved"]:
        # Атомарно: «решено» и очки — один раз
        done = await session.execute(
            update(TutorSession)
            .where(TutorSession.id == tutor.id, TutorSession.status == "active")
            .values(status="solved", points=_points(explain))
        )
        if done.rowcount:
            add_points(student, _points(explain))
    await mark_active(session, student, today)
    await session.commit()
    await session.refresh(tutor)
    return tutor


async def recent(session: AsyncSession, student_id: int, limit: int = 20) -> list[TutorSession]:
    rows = await session.scalars(
        select(TutorSession)
        .where(TutorSession.student_id == student_id)
        .order_by(desc(TutorSession.updated_at), desc(TutorSession.id))
        .limit(limit)
    )
    return list(rows)


def public(tutor: TutorSession) -> dict:
    return {
        "id": tutor.id,
        "title": tutor.title,
        "problem": tutor.problem,
        "subject": tutor.subject,
        "status": tutor.status,
        "points": tutor.points,
        "messages": [{"role": m["role"], "text": m["text"], "at": m["at"]} for m in tutor.messages],
        "turns_left": max(0, TUTOR_MAX_TURNS - sum(m["role"] == "student" for m in tutor.messages)),
        "updated_at": tutor.updated_at.isoformat() + "Z" if tutor.updated_at else None,
    }
