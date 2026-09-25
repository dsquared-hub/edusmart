"""«Не понял тему» — единый сценарий для бота и сайта.

Все изменения прогресса (лимит, очки, серия, шаги, завершение) идут только
через ExplainService, поэтому бот и сайт ведут себя одинаково, а тему можно
начать в одном месте и продолжить в другом с того же шага.

Качество ответов модели:
1. арифметика в вопросах пересчитывается кодом (app/services/checks.py);
2. второй, независимый запрос к модели решает каждый вопрос заново;
3. объяснение, не прошедшее проверку, генерируется заново (до 2 раз),
   иначе — честная ошибка вместо неверного урока;
4. ученик может нажать «⚠️ Здесь ошибка» — жалоба уходит учителю и владельцу.
"""
from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.timeutil import local_today, utcnow
from app.db.models import Student, Topic
from app.repositories import events as events_repo
from app.repositories import reports as reports_repo
from app.repositories import topics as topics_repo
from app.repositories import usage as usage_repo
from app.repositories.students import get_student
from app.services.accounts import consent_is_current
from app.services.checks import arithmetic_fix
from app.services.curriculum import match_topic
from app.services.gamification import add_points, mark_active
from app.services.gemini import LessonProvider

log = logging.getLogger(__name__)

EVENT_TOPIC_COMPLETED = "topic_completed"
EVENT_CONTENT_REPORT = "content_report"
MAX_TITLE_LENGTH = 500  # длиннее — просим сформулировать короче или прислать фото
GENERATION_ATTEMPTS = 2


# ---------- Ошибки сценария (code — ключ перевода и код ошибки API) ----------

class ExplainError(Exception):
    code = "explain_error"
    status = 400

    def __init__(self, topic: Topic | None = None):
        super().__init__(self.code)
        self.topic = topic


class NotStudent(ExplainError):
    code, status = "not_student", 403


class ConsentRequired(ExplainError):
    code, status = "consent_required", 403


class LimitReached(ExplainError):
    code, status = "limit_reached", 429


class SimplifyLimit(ExplainError):
    """Шаг упрощали уже N раз или кончился дневной лимит упрощений."""

    code, status = "simplify_limit", 429


class TopicTooLong(ExplainError):
    code, status = "topic_too_long", 422


class GenerationFailed(ExplainError):
    code, status = "generation_failed", 502


class TopicNotFound(ExplainError):
    code, status = "topic_not_found", 404


class TopicClosed(ExplainError):
    code, status = "topic_closed", 409


class StaleStep(ExplainError):
    """Шаг уже пройден в другом месте (например, на сайте, а кнопка — в боте)."""

    code, status = "stale_step", 409


class BadOption(ExplainError):
    code, status = "bad_option", 400


@dataclass
class AnswerResult:
    correct: bool
    topic: Topic
    points_awarded: int
    completed: bool
    total_points: int
    streak: int
    attempts: int = 1  # с какой попытки ответ верный


def points_for_attempt(wrong_before: int, settings: Settings) -> int:
    """10 — с первой попытки, 5 — со второй, дальше 0: перебором очки не набрать."""
    if wrong_before == 0:
        return settings.points_per_step
    if wrong_before == 1:
        return settings.points_second_try
    return 0


class ExplainService:
    def __init__(self, lesson: LessonProvider, settings: Settings | None = None):
        self.lesson = lesson
        self.settings = settings or get_settings()

    # ---------- Проверки ----------

    async def ensure_can_start(self, session: AsyncSession, user_id: int) -> Student:
        """Ученик, согласие родителя на текущую версию политики, лимит (без резервирования)."""
        student = await get_student(session, user_id)
        if student is None:
            raise NotStudent()
        if not consent_is_current(student, self.settings.policy_version):
            raise ConsentRequired()
        used = await usage_repo.used_today(session, user_id, local_today())
        if used >= self.settings.daily_explain_limit:
            raise LimitReached()
        return student

    async def remaining_today(self, session: AsyncSession, user_id: int) -> int:
        used = await usage_repo.used_today(session, user_id, local_today())
        return max(0, self.settings.daily_explain_limit - used)

    async def get_owned(
        self, session: AsyncSession, user_id: int, topic_id: int, *, for_update: bool = False
    ) -> Topic:
        topic = await topics_repo.get_topic(session, topic_id, for_update=for_update)
        if topic is None or topic.student_user_id != user_id:
            raise TopicNotFound()
        return topic

    # ---------- Проверка качества ответов модели ----------

    async def _problems(self, items: list[dict]) -> list[int]:
        """Индексы вопросов, где отмеченный ответ неверен (арифметика + проверяющий)."""
        bad = [
            i
            for i, item in enumerate(items)
            if arithmetic_fix(item["question"], item["options"], item["correct"]) is not None
        ]
        if bad or not self.settings.verify_explanations:
            return bad
        try:
            verdicts = await self.lesson.verify_answers(items)
        except Exception as exc:
            # Проверяющий недоступен: арифметику уже проверили, не блокируем ребёнка
            log.warning("Проверка ответов недоступна: %s", exc)
            return []
        return [
            i
            for i, (item, verdict) in enumerate(zip(items, verdicts))
            if not verdict["ok"] or verdict["correct"] != item["correct"]
        ]

    async def _generate_checked(
        self, generate: Callable[[], Awaitable[list[dict]]], to_items: Callable[[list[dict]], list[dict]]
    ) -> list[dict]:
        """Генерирует, проверяет; при ошибках — заново. Не прошло — GenerationFailed:
        лучше честно сказать «не получилось», чем научить ребёнка неправильному."""
        for attempt in range(1, GENERATION_ATTEMPTS + 1):
            result = await generate()
            problems = await self._problems(to_items(result))
            if not problems:
                return result
            log.warning("Ответ модели не прошёл проверку (попытка %s): вопросы %s", attempt, problems)
        raise GenerationFailed()

    @staticmethod
    def _step_items(steps: list[dict]) -> list[dict]:
        return [
            {
                "question": s["check_question"],
                "options": s["options"],
                "correct": s["correct"],
                "context": f"{s['title']}. {s['text']} {s['example']}",
            }
            for s in steps
        ]

    @staticmethod
    def _task_items(tasks: list[dict]) -> list[dict]:
        return [
            {"question": t["question"], "options": t["options"], "correct": t["correct"], "context": ""}
            for t in tasks
        ]

    # ---------- Сценарий ----------

    async def start(
        self,
        session: AsyncSession,
        user_id: int,
        title: str,
        *,
        photo: bytes | None = None,
        photo_mime: str | None = None,
        subject: str | None = None,
        grade: int | None = None,
        source: str = "web",
        lang: str = "ru",
    ) -> Topic:
        """Резервирует попытку, запрашивает и проверяет объяснение, создаёт тему.

        Фото живёт только в памяти этого вызова и никуда не сохраняется.
        """
        if len(title) > MAX_TITLE_LENGTH:
            raise TopicTooLong()
        await self.ensure_can_start(session, user_id)
        today = local_today()
        if not await usage_repo.try_reserve(
            session, user_id, today, self.settings.daily_explain_limit
        ):
            raise LimitReached()
        # Фиксируем резерв до долгого запроса к модели — не держим транзакцию.
        await session.commit()

        async def generate() -> list[dict]:
            return await self.lesson.explain_topic(
                title, photo=photo, photo_mime=photo_mime, subject=subject, grade=grade, lang=lang
            )

        try:
            steps = await self._generate_checked(generate, self._step_items)
        except Exception as exc:
            log.warning("Объяснение не получено: %s", exc)
            await usage_repo.refund(session, user_id, today)
            await session.commit()
            raise GenerationFailed() from exc

        student = await get_student(session, user_id)
        await mark_active(session, student, today)
        if grade and not student.grade:
            student.grade = grade
        topic = await topics_repo.create_topic(
            session,
            student_user_id=user_id,
            title=title[:255],  # полный текст ушёл модели, в списке тем хватит начала
            steps=steps,
            subject=subject,
            grade=grade,
            source=source,
        )
        # Привязка к теме школьной программы — для вечернего теста и ERS (без запроса к ИИ)
        topic.curriculum_topic_id = await match_topic(session, title, subject, grade or student.grade)
        await session.commit()
        return topic

    async def answer(
        self,
        session: AsyncSession,
        user_id: int,
        topic_id: int,
        step_index: int,
        option: int,
        *,
        advance_on_wrong: bool = False,
    ) -> AnswerResult:
        """Ответ на вопрос шага.

        По умолчанию (сайт) неверный ответ оставляет ученика на том же шаге.
        advance_on_wrong=True (бот): после неверного ответа бот сразу разбирает
        выбранный вариант и показывает верный — шаг закрывается без очков.
        """
        topic = await self.get_owned(session, user_id, topic_id, for_update=True)
        if topic.status != "in_progress":
            raise TopicClosed(topic)
        if step_index != topic.current_step:
            raise StaleStep(topic)
        step = topic.steps[step_index]
        if not (0 <= option < len(step["options"])):
            raise BadOption(topic)

        student = await get_student(session, user_id)
        correct = option == step["correct"]

        if not correct and not advance_on_wrong:
            topic.wrong_count += 1
            await session.commit()
            return AnswerResult(
                False, topic, 0, False, student.points, student.streak, topic.wrong_count
            )

        wrong_before = topic.wrong_count if correct else topic.wrong_count + 1
        points = points_for_attempt(wrong_before, self.settings) if correct else 0
        today = local_today()
        add_points(student, points)
        await mark_active(session, student, today)
        await topics_repo.record_attempt(
            session, topic.id, step_index, success=correct, wrong_count=wrong_before
        )
        topic.points_earned += points
        topic.current_step += 1
        topic.wrong_count = 0

        completed = topic.current_step >= topic.total_steps
        if completed:
            topic.status = "completed"
            topic.completed_at = utcnow()
            await events_repo.enqueue(
                session,
                EVENT_TOPIC_COMPLETED,
                {
                    "topic_id": topic.id,
                    "student_user_id": user_id,
                    "title": topic.title,
                    "points_earned": topic.points_earned,
                    "source": topic.source,
                },
            )
        await session.commit()
        return AnswerResult(
            correct, topic, points, completed, student.points, student.streak, wrong_before + 1
        )

    async def simplify(
        self, session: AsyncSession, user_id: int, topic_id: int, lang: str = "ru"
    ) -> dict:
        """Новый, более простой вариант текущего шага. Вопрос остаётся прежним.

        Каждое упрощение — платный запрос, поэтому: не больше simplify_per_step
        на шаг и daily_simplify_limit в день.
        """
        topic = await self.get_owned(session, user_id, topic_id)
        if topic.status != "in_progress":
            raise TopicClosed(topic)
        index = topic.current_step
        step = topic.steps[index]
        if step.get("simplify_count", 0) >= self.settings.simplify_per_step:
            raise SimplifyLimit(topic)
        today = local_today()
        if not await usage_repo.try_reserve(
            session, user_id, today, self.settings.daily_simplify_limit, counter="simplifications"
        ):
            raise SimplifyLimit(topic)
        title, total = topic.title or "", topic.total_steps
        await session.commit()  # не держим транзакцию во время запроса к модели

        try:
            simpler = await self.lesson.explain_step_simpler(title, step, index, total, lang=lang)
        except Exception as exc:
            log.warning("Упрощение не получено: %s", exc)
            await usage_repo.refund(session, user_id, today, counter="simplifications")
            await session.commit()
            raise GenerationFailed(topic) from exc

        simpler = {
            "title": simpler.get("title", ""),
            "text": simpler.get("text", ""),
            "example": simpler.get("example", ""),
            "visual": simpler.get("visual"),
        }
        # Сохраняем упрощение, чтобы после паузы ученик увидел его снова.
        topic = await self.get_owned(session, user_id, topic_id, for_update=True)
        if topic.status == "in_progress" and topic.current_step == index:
            steps = copy.deepcopy(topic.steps)
            steps[index]["simpler"] = simpler
            steps[index]["simplify_count"] = steps[index].get("simplify_count", 0) + 1
            topic.steps = steps
            await session.commit()
        return simpler

    async def practice(
        self, session: AsyncSession, user_id: int, topic_id: int, lang: str = "ru"
    ) -> list[dict]:
        """3 задачи для закрепления закрытой темы (генерируются и проверяются один раз)."""
        topic = await self.get_owned(session, user_id, topic_id)
        if topic.status != "completed":
            raise TopicClosed(topic)
        if topic.practice:
            return topic.practice
        title, steps = topic.title or "", topic.steps
        await session.commit()

        async def generate() -> list[dict]:
            return await self.lesson.make_practice(title, steps, lang=lang)

        try:
            tasks = await self._generate_checked(generate, self._task_items)
        except Exception as exc:
            raise GenerationFailed(topic) from exc
        topic = await self.get_owned(session, user_id, topic_id)
        topic.practice = tasks
        await session.commit()
        return tasks

    async def report(
        self,
        session: AsyncSession,
        user_id: int,
        topic_id: int,
        step_index: int,
        *,
        kind: str = "step",
        comment: str | None = None,
    ) -> bool:
        """«⚠️ Здесь ошибка». True — жалоба принята, False — уже была от этого ученика."""
        topic = await self.get_owned(session, user_id, topic_id)
        items = topic.steps if kind == "step" else (topic.practice or [])
        if not (0 <= step_index < len(items)):
            raise BadOption(topic)
        if await reports_repo.already_reported(session, topic.id, step_index, kind, user_id):
            return False
        report = await reports_repo.create_report(
            session,
            topic_id=topic.id,
            step_index=step_index,
            kind=kind,
            reporter_user_id=user_id,
            comment=(comment or "").strip()[:500] or None,
        )
        await events_repo.enqueue(
            session, EVENT_CONTENT_REPORT, {"report_id": report.id, "topic_id": topic.id}
        )
        await session.commit()
        return True


def topic_public(topic: Topic, settings: Settings | None = None) -> dict:
    """Тема для клиента: без правильных ответов на непройденные шаги."""
    settings = settings or get_settings()
    steps = []
    for i, step in enumerate(topic.steps or []):
        item = {k: step.get(k) for k in ("title", "text", "example", "visual", "check_question", "options")}
        item["simpler"] = step.get("simpler")
        item["simplify_left"] = max(0, settings.simplify_per_step - step.get("simplify_count", 0))
        if i < topic.current_step or topic.status == "completed":
            item["correct"] = step.get("correct")
        steps.append(item)
    return {
        "id": topic.id,
        "title": topic.title,
        "subject": topic.subject,
        "grade": topic.grade,
        "status": topic.status,
        "source": topic.source,
        "current_step": topic.current_step,
        "total_steps": topic.total_steps,
        "wrong_count": topic.wrong_count,
        "points_earned": topic.points_earned,
        "steps": steps,
        "practice": topic.practice,
        "created_at": topic.created_at.isoformat() if topic.created_at else None,
        "completed_at": topic.completed_at.isoformat() if topic.completed_at else None,
    }
