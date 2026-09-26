"""Квесты Paper-to-Digital (Dev-Spec, блок 1): реши задачу в тетради — сфоткай — EduCoin ×2.

Задача берётся из закрепления уже пройденной темы (explain.practice: 3 задачи, их ответы
проверены при генерации). Ученик решает на бумаге, фото проверяет та же Vision-модель,
что проверяет работы для учителя: распознаёт запись, сверяет с ключом, оценивает почерк.

Коины — только за полностью верное решение, и только если второй независимый запрос
к модели это подтвердил (правило проекта: ответ модели всегда проверяется). Фото живёт
только в памяти запроса. Квестов в день — PAPER_QUESTS_PER_DAY, попыток — ATTEMPTS.
"""
from __future__ import annotations

import logging
from datetime import datetime, time

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.timeutil import local_today, utcnow
from app.db.models import PaperQuest, Student, Topic, User
from app.services.explain import ExplainService
from app.services.gamification import mark_active
from app.services.vision import CheckTask, WorkChecker

log = logging.getLogger(__name__)

MAX_SCORE = 5
MIN_CONFIDENCE = 70  # ниже — просим переснять, коины не даём
DIGITAL_COINS = 3  # столько даёт похожее задание на экране (Stories с верными ответами)
PAPER_MULTIPLIER = 2  # на бумаге — вдвое больше
QUEST_COINS = DIGITAL_COINS * PAPER_MULTIPLIER
ATTEMPTS = 3
PAPER_QUESTS_PER_DAY = 5


class QuestError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


def _utc_day_start() -> datetime:
    """Начало сегодняшнего дня по Ташкенту — в наивном UTC, как в БД."""
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(get_settings().timezone)
    local = datetime.combine(local_today(), time(0), tzinfo=tz)
    return local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


async def create(session: AsyncSession, explain: ExplainService, user: User, topic_id: int) -> PaperQuest:
    """Квест по пройденной теме: следующая задача закрепления, которой ещё не было."""
    topic = await session.get(Topic, topic_id)
    if topic is None or topic.student_user_id != user.id:
        raise QuestError("topic_not_found", 404)
    if topic.status != "completed":
        raise QuestError("topic_not_completed", 409)
    # Незавершённый квест по этой теме — продолжаем его, а не создаём новый
    open_quest = await session.scalar(
        select(PaperQuest).where(
            PaperQuest.student_id == user.id, PaperQuest.topic_id == topic_id, PaperQuest.status == "open"
        )
    )
    if open_quest is not None:
        return open_quest
    today_count = await session.scalar(
        select(func.count(PaperQuest.id)).where(
            PaperQuest.student_id == user.id, PaperQuest.created_at >= _utc_day_start()
        )
    )
    if today_count >= PAPER_QUESTS_PER_DAY:
        raise QuestError("quests_limit", 429)
    tasks = await explain.practice(session, user.id, topic_id, lang=user.lang)  # проверены при генерации
    used = set(
        await session.scalars(
            select(PaperQuest.task_index).where(PaperQuest.student_id == user.id, PaperQuest.topic_id == topic_id)
        )
    )
    free = [i for i in range(len(tasks)) if i not in used]
    if not free:
        raise QuestError("quests_done", 409)
    index = free[0]
    task = tasks[index]
    quest = PaperQuest(
        student_id=user.id,
        topic_id=topic_id,
        task_index=index,
        task=task["question"],
        answer=task["options"][task["correct"]][:255],
    )
    session.add(quest)
    await session.commit()
    return quest


async def get_owned(session: AsyncSession, student_id: int, quest_id: int) -> PaperQuest:
    quest = await session.get(PaperQuest, quest_id)
    if quest is None or quest.student_id != student_id:
        raise QuestError("quest_not_found", 404)
    return quest


async def check_photo(
    session: AsyncSession,
    checker: WorkChecker,
    student: Student,
    user: User,
    quest_id: int,
    photo: bytes,
    mime: str,
) -> dict:
    quest = await get_owned(session, student.user_id, quest_id)
    if quest.status == "passed":
        raise QuestError("quest_passed", 409)
    if quest.attempts >= ATTEMPTS:
        raise QuestError("quest_attempts", 429)
    topic = await session.get(Topic, quest.topic_id)
    task = CheckTask(
        task_text=quest.task,
        answer_key=quest.answer,
        max_score=MAX_SCORE,
        subject=topic.subject if topic else None,
        grade=topic.grade if topic else student.grade,
        lang=user.lang,
    )
    # Попытку засчитываем до запроса: сбой модели её не «съест» — вернём ниже
    claimed = await session.execute(
        update(PaperQuest)
        .where(PaperQuest.id == quest.id, PaperQuest.status == "open", PaperQuest.attempts < ATTEMPTS)
        .values(attempts=PaperQuest.attempts + 1)
    )
    if not claimed.rowcount:
        raise QuestError("quest_attempts", 429)
    await session.commit()
    try:
        result = await checker.check_work(photo, mime, task)
        solved = result["score"] == MAX_SCORE and result["confidence"] >= MIN_CONFIDENCE
        if solved:
            # Второй независимый запрос: коины — только если он тоже видит верное решение
            second = await checker.check_work(photo, mime, task)
            solved = second["score"] == MAX_SCORE and second["confidence"] >= MIN_CONFIDENCE
    except Exception as exc:
        log.warning("Проверка квеста не удалась: %s", exc)
        await session.execute(
            update(PaperQuest).where(PaperQuest.id == quest.id).values(attempts=PaperQuest.attempts - 1)
        )
        await session.commit()
        raise QuestError("check_failed", 502) from exc

    blurry = result["confidence"] < MIN_CONFIDENCE
    values = {"score": result["score"], "neatness": result.get("neatness"), "comment": result.get("comment") or ""}
    awarded = False
    if solved:
        done = await session.execute(
            update(PaperQuest)
            .where(PaperQuest.id == quest.id, PaperQuest.status == "open")
            .values(status="passed", coins=QUEST_COINS, passed_at=utcnow(), **values)
        )
        awarded = bool(done.rowcount)
        if awarded:
            await session.execute(
                update(Student).where(Student.user_id == student.user_id).values(coins=Student.coins + QUEST_COINS)
            )
    else:
        await session.execute(update(PaperQuest).where(PaperQuest.id == quest.id).values(**values))
    await mark_active(session, student, local_today())
    await session.commit()
    await session.refresh(quest)
    await session.refresh(student)
    return {
        "quest": public(quest),
        "passed": quest.status == "passed",
        "awarded": awarded,
        "blurry": blurry,
        "marks": result.get("marks", []),
        "total_coins": student.coins,
    }


async def recent(session: AsyncSession, student_id: int, limit: int = 30) -> list[PaperQuest]:
    rows = await session.scalars(
        select(PaperQuest)
        .where(PaperQuest.student_id == student_id)
        .order_by(PaperQuest.status.desc(), desc(PaperQuest.created_at), desc(PaperQuest.id))  # open > passed
        .limit(limit)
    )
    return list(rows)


def public(quest: PaperQuest) -> dict:
    return {
        "id": quest.id,
        "topic_id": quest.topic_id,
        "task": quest.task,
        # Ключ показываем только после того, как квест пройден или попытки кончились
        "answer": quest.answer if quest.status == "passed" or quest.attempts >= ATTEMPTS else None,
        "status": quest.status,
        "attempts_left": max(0, ATTEMPTS - quest.attempts),
        "score": quest.score,
        "max_score": MAX_SCORE,
        "neatness": quest.neatness,
        "comment": quest.comment,
        "coins": quest.coins,
        "reward": QUEST_COINS,
        "created_at": quest.created_at.isoformat() + "Z" if quest.created_at else None,
    }

