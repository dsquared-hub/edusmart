"""Вечерний мини-тест (Модуль 4, п. 2.2).

Окно 17:00–22:00 по Ташкенту, ~2 минуты: 5–7 вопросов по темам, пройденным
сегодня, и 1–2 на интервальное повторение (темы 3, 7 и 14 дней назад).
Сложность адаптивная: верно — следующий вопрос сложнее, ошибка — проще.
Без наказания: после ошибки — объяснение и вторая попытка, за исправление монеты.
По завершении — пересчёт ERS и сообщение родителям через очередь событий.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.timeutil import local_now, utcnow
from app.db.models import Attempt, BankQuestion, CurriculumTopic, DailyTest, Student, Topic, User
from app.repositories import events as events_repo
from app.services import readiness
from app.services.accounts import consent_is_current
from app.services.gamification import add_points, mark_active
from app.services.questions import QuestionGenerator, pick_question

EVENT_EVENING_DONE = "evening_done"  # тест пройден — родителям в бот
MAX_TOPICS = 5
MAIN_MIN, MAIN_MAX, REVIEW_MAX = 5, 7, 2


class EveningError(Exception):
    def __init__(self, code: str, status: int = 409):
        super().__init__(code)
        self.code = code
        self.status = status


def _hm(value: str) -> time:
    h, m = value.split(":")
    return time(int(h), int(m))


def window_open(now: datetime, settings: Settings) -> bool:
    return _hm(settings.evening_start) <= now.time() < _hm(settings.evening_end)


def _utc_bounds(day: date, settings: Settings) -> tuple[datetime, datetime]:
    """Сутки по Ташкенту → границы в наивном UTC (так хранятся даты в БД)."""
    tz = ZoneInfo(settings.timezone)
    start = datetime.combine(day, time(0), tz).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    return start, start + timedelta(days=1)


async def _topics_on(session: AsyncSession, student_id: int, since: datetime, until: datetime) -> list[int]:
    """Темы программы, которыми ученик занимался в промежутке (новые — первыми)."""
    explained = await session.execute(
        select(Topic.curriculum_topic_id, Topic.created_at).where(
            Topic.student_user_id == student_id, Topic.curriculum_topic_id.is_not(None),
            Topic.created_at >= since, Topic.created_at < until,
        )
    )
    answered = await session.execute(
        select(Attempt.topic_id, Attempt.created_at).where(
            Attempt.student_id == student_id, Attempt.created_at >= since, Attempt.created_at < until, Attempt.source != "evening"
        )
    )
    seen: dict[int, datetime] = {}
    for topic_id, at in [*explained.all(), *answered.all()]:
        seen[topic_id] = max(seen.get(topic_id, at), at)
    return [t for t, _ in sorted(seen.items(), key=lambda kv: kv[1], reverse=True)]


async def plan_topics(session: AsyncSession, student_id: int, today: date, settings: Settings) -> tuple[list[int], list[int]]:
    """(темы сегодняшнего дня, темы на повторение)."""
    main = (await _topics_on(session, student_id, *_utc_bounds(today, settings)))[:MAX_TOPICS]
    if not main:
        # Сегодня тем не было — берём последние за неделю, чтобы тест всё равно имел смысл
        since, _ = _utc_bounds(today - timedelta(days=7), settings)
        main = (await _topics_on(session, student_id, since, _utc_bounds(today, settings)[0]))[:MAX_TOPICS]
    review: list[int] = []
    for days in (int(d) for d in settings.evening_review_days.split(",")):
        for topic_id in await _topics_on(session, student_id, *_utc_bounds(today - timedelta(days=days), settings)):
            if topic_id not in main and topic_id not in review:
                review.append(topic_id)
    return main, review[:REVIEW_MAX]


@dataclass
class Answered:
    correct: bool
    finished: bool
    retry: bool  # после ошибки: объяснение и ещё попытка
    explanation: str | None
    correct_option: int | None  # раскрываем после второй ошибки
    points: int


def _lang(user: User) -> str:
    return user.lang if user.lang in ("ru", "uz", "en") else "ru"


async def status(session: AsyncSession, user: User, settings: Settings | None = None, now: datetime | None = None) -> dict:
    settings = settings or get_settings()
    now = now or local_now()
    test = await session.scalar(select(DailyTest).where(DailyTest.student_id == user.id, DailyTest.date == now.date()))
    return {
        "open": window_open(now, settings),
        "window": [settings.evening_start, settings.evening_end],
        "test": None if test is None else {"id": test.id, "status": test.status, "score": test.score, "total": len(test.slots)},
    }


async def start(
    session: AsyncSession, user: User, generator: QuestionGenerator,
    settings: Settings | None = None, now: datetime | None = None,
) -> DailyTest:
    settings = settings or get_settings()
    now = now or local_now()
    student = await session.get(Student, user.id)
    if student is None:
        raise EveningError("not_student", 403)
    if not consent_is_current(student):
        raise EveningError("consent_required", 403)  # без согласия данные ребёнка ИИ не обрабатываются
    if not window_open(now, settings):
        raise EveningError("evening_closed", 409)
    existing = await session.scalar(select(DailyTest).where(DailyTest.student_id == user.id, DailyTest.date == now.date()))
    if existing is not None:
        if existing.status == "finished":
            raise EveningError("evening_done", 409)
        return existing  # продолжаем начатый тест
    main, review = await plan_topics(session, user.id, now.date(), settings)
    if not main and not review:
        raise EveningError("nothing_to_test", 409)
    main = main or review
    count = max(MAIN_MIN, min(MAIN_MAX, MAIN_MIN + len(main) - 1))
    slots = [{"topic_id": main[i % len(main)], "review": False} for i in range(count)]
    slots += [{"topic_id": t, "review": True} for t in review]
    test = DailyTest(
        student_id=user.id, date=now.date(), status="active", topic_ids=sorted(set(main + review)),
        slots=slots, current=0, difficulty=2, retry=False, score=0, corrected=0,
    )
    session.add(test)
    await session.flush()
    await ensure_question(session, test, user, generator)
    if not test.slots:  # ни по одной теме не нашлось вопросов (ИИ недоступен)
        await session.rollback()
        raise EveningError("nothing_to_test", 409)
    await session.commit()
    return test


async def _seen_questions(session: AsyncSession, student_id: int) -> set[int]:
    since = utcnow() - timedelta(days=14)
    rows = await session.scalars(
        select(Attempt.question_id).where(Attempt.student_id == student_id, Attempt.created_at >= since, Attempt.question_id.is_not(None))
    )
    return set(rows)


async def ensure_question(session: AsyncSession, test: DailyTest, user: User, generator: QuestionGenerator) -> None:
    """Вопрос для текущего слота подбирается в момент, когда до него дошли, —
    по сложности, заработанной предыдущими ответами."""
    if test.status != "active" or test.current >= len(test.slots):
        return
    slot = test.slots[test.current]
    if slot.get("question_id"):
        return
    topic = await session.get(CurriculumTopic, slot["topic_id"])
    exclude = await _seen_questions(session, user.id) | {s["question_id"] for s in test.slots if s.get("question_id")}
    question = await pick_question(session, generator, topic, test.difficulty, _lang(user), exclude)
    slots = [dict(s) for s in test.slots]  # новый список — иначе ORM не заметит изменения JSON
    if question is None:
        slots.pop(test.current)  # по теме нет вопросов даже после генерации — пропускаем слот
    else:
        slots[test.current]["question_id"] = question.id
        slots[test.current]["difficulty"] = test.difficulty
    test.slots = slots
    if question is None:
        if test.current >= len(test.slots):
            return
        await ensure_question(session, test, user, generator)


async def get_test(session: AsyncSession, user: User, test_id: int) -> DailyTest:
    test = await session.get(DailyTest, test_id)
    if test is None or test.student_id != user.id:
        raise EveningError("test_not_found", 404)
    return test


async def question_view(session: AsyncSession, test: DailyTest, user: User) -> dict | None:
    """Текущий вопрос для клиента — без правильного ответа."""
    if test.status != "active" or test.current >= len(test.slots):
        return None
    slot = test.slots[test.current]
    question = await session.get(BankQuestion, slot["question_id"])
    topic = await session.get(CurriculumTopic, slot["topic_id"])
    return {
        "slot": test.current,
        "total": len(test.slots),
        "question": question.question,
        "options": question.options,
        "difficulty": slot.get("difficulty", test.difficulty),
        "review": slot["review"],
        "topic": topic.name(_lang(user)) if topic else "",
        "retry": test.retry,
    }


async def answer(
    session: AsyncSession, user: User, test_id: int, slot: int, option: int, time_ms: int,
    generator: QuestionGenerator, settings: Settings | None = None, now: datetime | None = None,
) -> tuple[DailyTest, Answered]:
    settings = settings or get_settings()
    test = await get_test(session, user, test_id)
    if test.status != "active":
        raise EveningError("evening_done")
    if slot != test.current:
        raise EveningError("stale_slot")  # ответ на уже пройденный вопрос (двойной клик, вторая вкладка)
    slots = [dict(s) for s in test.slots]
    current = slots[test.current]
    question = await session.get(BankQuestion, current["question_id"])
    if not 0 <= option < len(question.options):
        raise EveningError("bad_option", 422)
    student = await session.get(Student, user.id)
    correct = option == question.correct
    points = 0

    if not test.retry:
        # Для освоения и ERS считается только первая попытка
        session.add(Attempt(
            student_id=user.id, topic_id=current["topic_id"], question_id=question.id, is_correct=correct,
            time_ms=max(0, min(time_ms, 10 * 60 * 1000)), is_review=current["review"], source="evening",
        ))
        if correct:
            points = settings.points_per_step
            current["result"] = "correct"
            test.score += 1
            test.difficulty = min(3, test.difficulty + 1)
        else:
            current["result"] = "wrong"
            test.retry = True
            test.slots = slots
            await session.commit()
            return test, Answered(False, False, True, question.explanation, None, 0)
    else:
        test.retry = False
        test.difficulty = max(1, test.difficulty - 1)
        if correct:
            points = settings.points_correction  # монеты за исправление — ошибка стала пониманием
            current["result"] = "corrected"
            test.corrected += 1
        else:
            current["result"] = "missed"

    add_points(student, points)
    test.slots = slots
    test.current += 1
    finished = test.current >= len(test.slots)
    if finished:
        await _finish(session, test, student, settings, now)
    else:
        await ensure_question(session, test, user, generator)
    await session.commit()
    reveal = question.correct if (not correct and current["result"] == "missed") else None
    return test, Answered(correct, finished, False, question.explanation if reveal is not None else None, reveal, points)


def summary(test: DailyTest) -> dict:
    """Итог по темам: тема «понята», если большинство её вопросов решено с первой попытки."""
    by_topic: dict[int, list[str]] = defaultdict(list)
    for s in test.slots:
        by_topic[s["topic_id"]].append(s.get("result", ""))
    understood = [t for t, results in by_topic.items() if results.count("correct") * 2 > len(results)]
    misses = Counter({t: sum(r != "correct" for r in results) for t, results in by_topic.items()})
    weak = [t for t, n in misses.most_common() if n > 0][:1]
    return {
        "score": test.score,
        "total": len(test.slots),
        "corrected": test.corrected,
        "topics_total": len(by_topic),
        "topics_understood": len(understood),
        "weak_topic_id": weak[0] if weak else None,
    }


async def _finish(session: AsyncSession, test: DailyTest, student: Student, settings: Settings, now: datetime | None) -> None:
    test.status = "finished"
    test.finished_at = utcnow()
    today = (now or local_now()).date()
    await mark_active(session, student, today, settings.freezes_per_week)
    subject_ids = set(
        await session.scalars(select(CurriculumTopic.subject_id).where(CurriculumTopic.id.in_(test.topic_ids)))
    )
    await session.flush()
    for subject_id in subject_ids:
        await readiness.compute(session, student.user_id, subject_id, settings)
    await events_repo.enqueue(session, EVENT_EVENING_DONE, {"test_id": test.id})
