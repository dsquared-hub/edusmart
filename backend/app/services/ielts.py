"""IELTS AI Coach (10–11 классы): все четыре секции в электронном виде.

Writing (Task 1 / Task 2): задание генерирует ИИ (для Task 1 — с данными графика, сайт
рисует его сам), ученик пишет эссе на сайте (черновик сохраняется). Оценивают ДВА
независимых экзаменатора по 4 официальным критериям (TR, CC, LR, GRA) — это и есть
проверка ответа модели вторым запросом. Балл критерия — среднее двух, итоговый Band
считает код по правилу IELTS (среднее четырёх, округление до 0.5; .25 → вверх до .5,
.75 → вверх до целого). Ошибки показываем только те, чья цитата действительно есть в эссе.

Задания общие для всех: новое генерируется, только когда ученик прошёл все имеющиеся.
Проверка эссе тратит одну попытку из дневного лимита объяснений.
"""
from __future__ import annotations

import asyncio
import logging
import math
import re

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import local_today, utcnow
from app.db.models import IeltsAttempt, IeltsMaterial, Student
from app.repositories import usage as usage_repo
from app.services.explain import ExplainService
from app.services.gamification import mark_active
from app.services.gemini import IELTS_CRITERIA_WRITING

log = logging.getLogger(__name__)

MIN_GRADE = 10  # спецификация: IELTS — для 10–11 классов
WRITING = {1: {"kind": "writing1", "minutes": 20, "min_words": 150}, 2: {"kind": "writing2", "minutes": 40, "min_words": 250}}
MIN_WORDS_TO_GRADE = 50
MAX_ESSAY_CHARS = 6000
AI_TIMEOUT = 90.0


class IeltsError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


def overall_band(bands: list[float]) -> float:
    """Правило IELTS: среднее, округлённое до 0.5 (6.25 → 6.5, 6.75 → 7.0, 6.125 → 6.0)."""
    mean = sum(bands) / len(bands)
    return math.floor(mean * 2 + 0.5) / 2


def average_band(a: float, b: float) -> float:
    return overall_band([a, b])


def count_words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9’'-]+", text))


def ensure_grade(student: Student) -> None:
    if student.grade is not None and student.grade < MIN_GRADE:
        raise IeltsError("ielts_grade", 403)


async def _material(session: AsyncSession, explain: ExplainService, student: Student, kind: str, make) -> IeltsMaterial:
    """Задание, которое ученик ещё не делал; все пройдены — ИИ генерирует новое."""
    done = select(IeltsAttempt.material_id).where(IeltsAttempt.student_id == student.user_id, IeltsAttempt.kind == kind)
    material = await session.scalar(
        select(IeltsMaterial).where(IeltsMaterial.kind == kind, IeltsMaterial.id.not_in(done)).order_by(IeltsMaterial.id)
    )
    if material is not None:
        return material
    try:
        content = await asyncio.wait_for(make(), AI_TIMEOUT)
    except Exception as exc:
        log.warning("IELTS: задание %s не сгенерировано: %s", kind, exc)
        raise IeltsError("generation_failed", 502) from exc
    material = IeltsMaterial(kind=kind, content=content)
    session.add(material)
    await session.flush()
    return material


# ---------- Writing ----------

async def start_writing(session: AsyncSession, explain: ExplainService, student: Student, task: int) -> IeltsAttempt:
    ensure_grade(student)
    if task not in WRITING:
        raise IeltsError("bad_task", 422)
    kind = WRITING[task]["kind"]
    active = await session.scalar(
        select(IeltsAttempt).where(
            IeltsAttempt.student_id == student.user_id, IeltsAttempt.kind == kind, IeltsAttempt.status == "active"
        )
    )
    if active is not None:
        return active  # незаконченное эссе — продолжаем его
    material = await _material(session, explain, student, kind, lambda: explain.lesson.ielts_writing_prompt(task))
    attempt = IeltsAttempt(student_id=student.user_id, material_id=material.id, kind=kind, answers={"text": ""})
    session.add(attempt)
    await session.commit()
    return attempt


async def get_owned(session: AsyncSession, student_id: int, attempt_id: int) -> tuple[IeltsAttempt, IeltsMaterial]:
    attempt = await session.get(IeltsAttempt, attempt_id)
    if attempt is None or attempt.student_id != student_id:
        raise IeltsError("ielts_not_found", 404)
    return attempt, await session.get(IeltsMaterial, attempt.material_id)


async def save_draft(session: AsyncSession, student_id: int, attempt_id: int, text: str) -> IeltsAttempt:
    attempt, _ = await get_owned(session, student_id, attempt_id)
    if attempt.status != "active" or not attempt.kind.startswith("writing"):
        raise IeltsError("ielts_done", 409)
    attempt.answers = {**(attempt.answers or {}), "text": text[:MAX_ESSAY_CHARS]}
    await session.commit()
    return attempt


def _real_errors(errors: list[dict], essay: str) -> list[dict]:
    """Только ошибки с цитатой, которая действительно есть в эссе (модель могла «придумать»)."""
    lower = essay.lower()
    seen, out = set(), []
    for e in errors:
        quote = e["quote"]
        key = quote.lower()
        if key in seen or key not in lower:
            continue
        seen.add(key)
        out.append(e)
    return out


async def submit_writing(
    session: AsyncSession, explain: ExplainService, student: Student, attempt_id: int, text: str
) -> IeltsAttempt:
    attempt, material = await get_owned(session, student.user_id, attempt_id)
    if attempt.status != "active" or not attempt.kind.startswith("writing"):
        raise IeltsError("ielts_done", 409)
    essay = text.strip()[:MAX_ESSAY_CHARS]
    words = count_words(essay)
    attempt.answers = {"text": essay}
    await session.commit()  # эссе сохраняем до проверки — при сбое ничего не пропадёт
    if words < MIN_WORDS_TO_GRADE:
        raise IeltsError("essay_too_short", 422)
    await explain.ensure_can_start(session, student.user_id)  # согласие и лимит
    today = local_today()
    if not await usage_repo.try_reserve(session, student.user_id, today, explain.settings.daily_explain_limit):
        raise IeltsError("limit_reached", 429)
    await session.commit()

    task = material.content["task"]
    lesson = explain.lesson
    try:
        a, b = await asyncio.wait_for(
            asyncio.gather(
                lesson.ielts_grade_writing(task, material.content["prompt"], essay, words, "A"),
                lesson.ielts_grade_writing(task, material.content["prompt"], essay, words, "B"),
            ),
            AI_TIMEOUT,
        )
    except Exception as exc:
        log.warning("IELTS Writing: оценка не получена: %s", exc)
        await usage_repo.refund(session, student.user_id, today)
        await session.commit()
        raise IeltsError("generation_failed", 502) from exc

    criteria = {
        key: {
            "band": average_band(a["criteria"][key]["band"], b["criteria"][key]["band"]),
            "comment": a["criteria"][key]["comment"] or b["criteria"][key]["comment"],
        }
        for key in IELTS_CRITERIA_WRITING
    }
    minimum = WRITING[task]["min_words"]
    attempt.result = {
        "criteria": criteria,
        "examiners": {
            name: {k: g["criteria"][k]["band"] for k in IELTS_CRITERIA_WRITING} for name, g in (("A", a), ("B", b))
        },
        "errors": _real_errors(a["errors"] + b["errors"], essay),
        "summary": a["summary"] or b["summary"],
        "improved": a["improved"] or b["improved"],
        "words": words,
        "min_words": minimum,
        "under_length": words < minimum,
    }
    attempt.band = overall_band([c["band"] for c in criteria.values()])
    attempt.status = "done"
    attempt.finished_at = utcnow()
    await mark_active(session, student, today)
    await session.commit()
    return attempt


# ---------- Reading / Listening ----------

TESTS = ("reading", "listening")
# Официальные таблицы пересчёта IELTS (Academic Reading / Listening): верных из 40 → Band.
READING_BANDS = ((39, 9.0), (37, 8.5), (35, 8.0), (33, 7.5), (30, 7.0), (27, 6.5), (23, 6.0), (19, 5.5),
                 (15, 5.0), (13, 4.5), (10, 4.0), (8, 3.5), (6, 3.0), (4, 2.5), (0, 0.0))
LISTENING_BANDS = ((39, 9.0), (37, 8.5), (35, 8.0), (32, 7.5), (30, 7.0), (26, 6.5), (23, 6.0), (18, 5.5),
                   (16, 5.0), (13, 4.5), (10, 4.0), (8, 3.5), (6, 3.0), (4, 2.5), (0, 0.0))


def test_band(kind: str, correct: int, total: int) -> float:
    """Наш тест короче настоящего (≈13 вопросов вместо 40) — приводим к шкале из 40."""
    scaled = round(correct * 40 / total) if total else 0
    table = READING_BANDS if kind == "reading" else LISTENING_BANDS
    return next(band for threshold, band in table if scaled >= threshold)


async def start_test(session: AsyncSession, explain: ExplainService, student: Student, kind: str) -> IeltsAttempt:
    ensure_grade(student)
    if kind not in TESTS:
        raise IeltsError("bad_task", 422)
    active = await session.scalar(
        select(IeltsAttempt).where(
            IeltsAttempt.student_id == student.user_id, IeltsAttempt.kind == kind, IeltsAttempt.status == "active"
        )
    )
    if active is not None:
        return active
    material = await _material(session, explain, student, kind, lambda: explain.lesson.ielts_test_material(kind))
    attempt = IeltsAttempt(student_id=student.user_id, material_id=material.id, kind=kind, answers={})
    session.add(attempt)
    await session.commit()
    return attempt


async def submit_test(session: AsyncSession, student: Student, attempt_id: int, answers: dict) -> IeltsAttempt:
    from app.services.gemini import ielts_answer_ok

    attempt, material = await get_owned(session, student.user_id, attempt_id)
    if attempt.status != "active" or attempt.kind not in TESTS:
        raise IeltsError("ielts_done", 409)
    questions = material.content["questions"]
    given = {str(k): v for k, v in (answers or {}).items()}
    marks = [ielts_answer_ok(q, given.get(str(i))) for i, q in enumerate(questions)]
    correct = sum(marks)
    attempt.answers = {str(i): given.get(str(i)) for i in range(len(questions))}
    attempt.result = {"correct": correct, "total": len(questions), "marks": marks, "scaled": round(correct * 40 / len(questions))}
    attempt.band = test_band(attempt.kind, correct, len(questions))
    attempt.status = "done"
    attempt.finished_at = utcnow()
    await mark_active(session, student, local_today())
    await session.commit()
    return attempt


def _public_material(attempt: IeltsAttempt, material: IeltsMaterial) -> dict:
    """Во время теста — без ключа и доказательств; после — всё для разбора."""
    content = material.content
    if attempt.status == "done" or attempt.kind not in TESTS:
        return content
    hidden = {"answer", "alternatives", "evidence"}
    return {**content, "questions": [{k: v for k, v in q.items() if k not in hidden} for q in content["questions"]]}


# ---------- Speaking ----------

MAX_AUDIO_BYTES = 8 * 1024 * 1024  # ~4 минуты WAV 16 кГц моно
AUDIO_MIME = {"audio/wav", "audio/x-wav", "audio/wave", "audio/webm", "audio/ogg", "audio/mpeg", "audio/mp4", "audio/aac"}


def speaking_plan(content: dict) -> list[dict]:
    """Порядок экзамена: Part 1 — 4 вопроса, Part 2 — карточка (1 длинный ответ), Part 3 — 4 вопроса."""
    card = content["part2"]
    cue = f"{card['topic']}. You should say: " + "; ".join(card["points"])
    return (
        [{"part": 1, "question": q} for q in content["part1"]]
        + [{"part": 2, "question": cue}]
        + [{"part": 3, "question": q} for q in content["part3"]]
    )


async def start_speaking(session: AsyncSession, explain: ExplainService, student: Student) -> IeltsAttempt:
    """Экзамен Speaking целиком тратит одну попытку из дневного лимита (при старте)."""
    ensure_grade(student)
    active = await session.scalar(
        select(IeltsAttempt).where(
            IeltsAttempt.student_id == student.user_id, IeltsAttempt.kind == "speaking", IeltsAttempt.status == "active"
        )
    )
    if active is not None:
        return active
    await explain.ensure_can_start(session, student.user_id)
    today = local_today()
    if not await usage_repo.try_reserve(session, student.user_id, today, explain.settings.daily_explain_limit):
        raise IeltsError("limit_reached", 429)
    await session.commit()
    try:
        material = await _material(session, explain, student, "speaking", explain.lesson.ielts_speaking_material)
    except IeltsError:
        await usage_repo.refund(session, student.user_id, today)
        await session.commit()
        raise
    attempt = IeltsAttempt(student_id=student.user_id, material_id=material.id, kind="speaking", answers={"turns": []})
    session.add(attempt)
    await session.commit()
    return attempt


def _heard(turn: dict) -> dict:
    """Замечания — только о том, что действительно есть в расшифровке."""
    text = turn["transcript"].lower()
    words = set(re.findall(r"[a-z’'-]+", text))
    return {
        **turn,
        "grammar": [g for g in turn["grammar"] if g["quote"].lower() in text],
        "vocabulary": [v for v in turn["vocabulary"] if v["quote"].lower() in text],
        "pronunciation": [p for p in turn["pronunciation"] if p["word"].lower() in words],
    }


async def speak(
    session: AsyncSession, explain: ExplainService, student: Student, attempt_id: int, turn: int, audio: bytes, mime: str
) -> IeltsAttempt:
    attempt, material = await get_owned(session, student.user_id, attempt_id)
    if attempt.kind != "speaking" or attempt.status != "active":
        raise IeltsError("ielts_done", 409)
    plan = speaking_plan(material.content)
    turns = list((attempt.answers or {}).get("turns", []))
    if turn != len(turns) or turn >= len(plan):
        raise IeltsError("stale_turn", 409)  # ответ на уже пройденный / не тот вопрос
    step = plan[turn]
    lesson = explain.lesson
    try:
        heard = await asyncio.wait_for(lesson.ielts_speaking_turn(step["part"], step["question"], audio, mime), AI_TIMEOUT)
    except Exception as exc:
        log.warning("IELTS Speaking: ответ не распознан: %s", exc)
        raise IeltsError("generation_failed", 502) from exc
    if len(heard["transcript"].split()) < 2:
        raise IeltsError("no_speech", 422)  # тишина или не по-английски — просим ответить ещё раз
    turns.append({**step, **_heard(heard)})
    attempt.answers = {"turns": turns}
    await session.commit()
    if len(turns) < len(plan):
        return attempt

    try:
        a, b = await asyncio.wait_for(
            asyncio.gather(lesson.ielts_grade_speaking(turns, "A"), lesson.ielts_grade_speaking(turns, "B")), AI_TIMEOUT
        )
    except Exception as exc:
        log.warning("IELTS Speaking: итоговая оценка не получена: %s", exc)
        raise IeltsError("generation_failed", 502) from exc  # ответы сохранены — «Оценить» можно повторить
    return await _finish_speaking(session, student, attempt, turns, a, b)


async def _finish_speaking(session, student, attempt, turns, a: dict, b: dict) -> IeltsAttempt:
    from app.services.gemini import IELTS_CRITERIA_SPEAKING

    criteria = {
        k: {"band": average_band(a["criteria"][k]["band"], b["criteria"][k]["band"]),
            "comment": a["criteria"][k]["comment"] or b["criteria"][k]["comment"]}
        for k in IELTS_CRITERIA_SPEAKING
    }
    attempt.result = {
        "criteria": criteria,
        "examiners": {n: {k: g["criteria"][k]["band"] for k in IELTS_CRITERIA_SPEAKING} for n, g in (("A", a), ("B", b))},
        "summary": a["summary"] or b["summary"],
    }
    attempt.band = overall_band([c["band"] for c in criteria.values()])
    attempt.status = "done"
    attempt.finished_at = utcnow()
    await mark_active(session, student, local_today())
    await session.commit()
    return attempt


async def grade_speaking(session: AsyncSession, explain: ExplainService, student: Student, attempt_id: int) -> IeltsAttempt:
    """Повторить итоговую оценку, если в прошлый раз модель не ответила (все ответы уже есть)."""
    attempt, material = await get_owned(session, student.user_id, attempt_id)
    turns = (attempt.answers or {}).get("turns", [])
    if attempt.kind != "speaking" or attempt.status != "active" or len(turns) < len(speaking_plan(material.content)):
        raise IeltsError("ielts_done", 409)
    lesson = explain.lesson
    try:
        a, b = await asyncio.wait_for(
            asyncio.gather(lesson.ielts_grade_speaking(turns, "A"), lesson.ielts_grade_speaking(turns, "B")), AI_TIMEOUT
        )
    except Exception as exc:
        raise IeltsError("generation_failed", 502) from exc
    return await _finish_speaking(session, student, attempt, turns, a, b)


# ---------- Общее ----------

async def recent(session: AsyncSession, student_id: int, limit: int = 30) -> list[IeltsAttempt]:
    rows = await session.scalars(
        select(IeltsAttempt)
        .where(IeltsAttempt.student_id == student_id)
        .order_by(desc(IeltsAttempt.started_at), desc(IeltsAttempt.id))
        .limit(limit)
    )
    return list(rows)


def brief(attempt: IeltsAttempt) -> dict:
    return {
        "id": attempt.id,
        "kind": attempt.kind,
        "status": attempt.status,
        "band": attempt.band,
        "started_at": attempt.started_at.isoformat() + "Z",
        "finished_at": attempt.finished_at.isoformat() + "Z" if attempt.finished_at else None,
    }


def public(attempt: IeltsAttempt, material: IeltsMaterial) -> dict:
    out = {**brief(attempt), "material": _public_material(attempt, material), "answers": attempt.answers, "result": attempt.result}
    if attempt.kind.startswith("writing"):
        spec = WRITING[material.content["task"]]
        out["limits"] = {"minutes": spec["minutes"], "min_words": spec["min_words"]}
    if attempt.kind == "speaking":
        out["plan"] = speaking_plan(material.content)
    return out


def overview(attempts: list[IeltsAttempt]) -> dict:
    """Лучший и последний Band по каждой секции."""
    best: dict[str, float] = {}
    for a in attempts:
        if a.band is not None:
            section = "writing" if a.kind.startswith("writing") else a.kind
            best[section] = max(best.get(section, 0.0), a.band)
    return {"best": best}

