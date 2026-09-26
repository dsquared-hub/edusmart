"""ДТМ-симулятор (Dev-Spec, блок 1): тренировочный вступительный тест в формате ДТМ.

Структура варианта (как на экзамене):
    3 обязательных блока × 10 вопросов × 1.1 балла — родной язык и литература,
      математика, история Узбекистана;
    1-й профильный предмет — 30 вопросов × 3.1 балла;
    2-й профильный предмет — 30 вопросов × 2.1 балла.
Всего 90 вопросов, 180 минут, максимум 189 баллов.

Вопросы — из банка dtm_questions. Не хватает — ИИ генерирует недостающее по разделам
предмета (для разнообразия), каждый ответ перепроверяется вторым запросом (вопросы
с сомнительным ответом в банк не попадают). Банк общий: первый вариант собирается
дольше, дальше — сразу. Ученик не получает вопросы, которые уже видел, пока банка хватает.

Время — по серверу: после deadline_at ответы не принимаются, вариант завершается сам.
Ответы можно менять до завершения, как на настоящем экзамене.
"""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import utcnow
from app.db.models import DtmQuestion, DtmTest, Student
from app.services.questions import QuestionGenerator, QuotaExceeded

log = logging.getLogger(__name__)

DURATION = timedelta(minutes=180)
MIN_GRADE = 8  # Dev-Spec: ДТМ-тренажёр — для 8–11 классов
GEN_BATCH = 10
GEN_TIMEOUT = 120.0


@dataclass(frozen=True)
class Subject:
    code: str
    names: dict[str, str]
    sections: tuple[str, ...]

    def name(self, lang: str) -> str:
        return self.names.get(lang) or self.names["ru"]


SUBJECTS: dict[str, Subject] = {
    s.code: s
    for s in (
        Subject("ona_tili", {"ru": "Родной язык и литература", "uz": "Ona tili va adabiyot", "en": "Native language and literature"},
                ("фонетика и орфография", "лексика и фразеология", "морфология", "синтаксис и пунктуация", "узбекская литература: авторы и произведения")),
        Subject("math", {"ru": "Математика", "uz": "Matematika", "en": "Mathematics"},
                ("проценты и пропорции", "уравнения и неравенства", "функции и графики", "прогрессии", "планиметрия", "тригонометрия", "текстовые задачи")),
        Subject("history_uz", {"ru": "История Узбекистана", "uz": "O‘zbekiston tarixi", "en": "History of Uzbekistan"},
                ("древние государства и Великий шёлковый путь", "эпоха Амира Темура и Темуридов", "ханства и Туркестанский край", "советский период", "независимый Узбекистан")),
        Subject("physics", {"ru": "Физика", "uz": "Fizika", "en": "Physics"},
                ("кинематика", "динамика и законы Ньютона", "работа, энергия, импульс", "термодинамика", "электричество", "оптика")),
        Subject("chemistry", {"ru": "Химия", "uz": "Kimyo", "en": "Chemistry"},
                ("строение атома и периодическая система", "химическая связь", "реакции и уравнения", "растворы и расчёты", "органическая химия")),
        Subject("biology", {"ru": "Биология", "uz": "Biologiya", "en": "Biology"},
                ("клетка", "генетика", "анатомия человека", "ботаника", "зоология", "экология и эволюция")),
        Subject("english", {"ru": "Английский язык", "uz": "Ingliz tili", "en": "English"},
                ("grammar: tenses", "grammar: articles and prepositions", "vocabulary", "reading comprehension", "word formation")),
        Subject("russian", {"ru": "Русский язык", "uz": "Rus tili", "en": "Russian"},
                ("орфография", "морфология", "синтаксис", "лексика", "пунктуация")),
        Subject("history", {"ru": "Всемирная история", "uz": "Jahon tarixi", "en": "World history"},
                ("древний мир", "средние века", "новое время", "новейшая история")),
        Subject("geography", {"ru": "География", "uz": "Geografiya", "en": "Geography"},
                ("физическая география", "климат и природные зоны", "население и экономика", "география Узбекистана")),
        Subject("law", {"ru": "Основы права", "uz": "Huquq asoslari", "en": "Law basics"},
                ("Конституция Республики Узбекистан", "гражданское право", "трудовое право", "права человека")),
    )
}

MANDATORY = ("ona_tili", "math", "history_uz")
SPEC_CHOICES = ("math", "physics", "chemistry", "biology", "english", "russian", "history", "geography", "ona_tili", "law")
# (блок, вопросов, баллов за вопрос)
BLOCKS = (("mandatory", 10, 1.1), ("spec1", 30, 3.1), ("spec2", 30, 2.1))
MAX_SCORE = round(sum(n * p for _, n, p in BLOCKS[:1]) * len(MANDATORY) + sum(n * p for _, n, p in BLOCKS[1:]), 1)


class DtmError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


def plan(spec1: str, spec2: str) -> list[tuple[str, str, int, float]]:
    """[(блок, предмет, вопросов, баллов за вопрос)] — порядок блоков как на экзамене."""
    count, weight = BLOCKS[0][1], BLOCKS[0][2]
    out = [(f"mandatory:{code}", code, count, weight) for code in MANDATORY]
    out.append(("spec1", spec1, BLOCKS[1][1], BLOCKS[1][2]))
    out.append(("spec2", spec2, BLOCKS[2][1], BLOCKS[2][2]))
    return out


async def generate_bank(
    session: AsyncSession, generator: QuestionGenerator, subject: Subject, lang: str, need: int, offset: int = 0
) -> int:
    """Недостающие вопросы: пачки по разделам ПО ОЧЕРЕДИ (параллельные запросы упираются в
    лимит ключа Gemini). В банк — только перепроверенные; каждая пачка сохраняется сразу,
    чтобы при обрыве ничего не терялось. Лимит ключа — останавливаемся (QuotaExceeded)."""
    added, batch = 0, offset
    attempts = max(1, -(-need // GEN_BATCH)) + 2  # пара запасных пачек на отбракованные вопросы
    for _ in range(attempts):
        if added >= need:
            break
        section = subject.sections[batch % len(subject.sections)]
        batch += 1
        try:
            items = await generator.generate(section, subject.names["ru"], 11, 2, lang, count=GEN_BATCH, purpose="dtm")
        except QuotaExceeded:
            raise
        except Exception as exc:  # одна неудачная пачка не должна валить весь вариант
            log.warning("ДТМ: вопросы %s / %s не сгенерированы: %s", subject.code, section, exc)
            continue
        session.add_all(DtmQuestion(subject=subject.code, section=section[:255], lang=lang, **q) for q in items)
        await session.commit()
        added += len(items)
    return added


async def _pick(
    session: AsyncSession, generator: QuestionGenerator, subject: Subject, lang: str, count: int, seen: set[int]
) -> list[DtmQuestion]:
    stmt = select(DtmQuestion).where(DtmQuestion.subject == subject.code, DtmQuestion.lang == lang)
    bank = list(await session.scalars(stmt))
    fresh = [q for q in bank if q.id not in seen]
    if len(fresh) < count:
        await asyncio.wait_for(
            generate_bank(session, generator, subject, lang, count - len(fresh), offset=len(bank) // GEN_BATCH),
            GEN_TIMEOUT,
        )
        bank = list(await session.scalars(stmt))
        fresh = [q for q in bank if q.id not in seen]
    if len(fresh) < count:
        # Не хватило новых — добираем уже виденными, лучше повтор, чем неполный вариант
        fresh += [q for q in bank if q.id in seen][: count - len(fresh)]
    if len(fresh) < count:
        raise DtmError("dtm_preparing", 503)  # сгенерированное сохранено — следующая попытка соберёт вариант
    return random.sample(fresh, count)


async def start(
    session: AsyncSession, generator: QuestionGenerator, student: Student, lang: str, spec1: str, spec2: str
) -> DtmTest:
    if student.grade is not None and student.grade < MIN_GRADE:
        raise DtmError("dtm_grade", 403)
    if spec1 not in SPEC_CHOICES or spec2 not in SPEC_CHOICES or spec1 == spec2:
        raise DtmError("dtm_bad_subjects", 422)
    active = await session.scalar(
        select(DtmTest).where(DtmTest.student_id == student.user_id, DtmTest.status == "active")
    )
    if active is not None:
        if active.deadline_at > utcnow():
            raise DtmError("dtm_active", 409)
        await finish(session, active)  # время старого варианта вышло — закрываем
    seen = {
        slot["question_id"]
        for slots in await session.scalars(select(DtmTest.slots).where(DtmTest.student_id == student.user_id))
        for slot in slots
    }
    slots = []
    for block, code, count, _weight in plan(spec1, spec2):
        try:
            questions = await _pick(session, generator, SUBJECTS[code], lang, count, seen)
        except asyncio.TimeoutError as exc:
            raise DtmError("dtm_preparing", 503) from exc  # готовые пачки уже сохранены
        except QuotaExceeded as exc:
            log.warning("ДТМ: лимит ключа Gemini исчерпан: %s", exc)
            raise DtmError("ai_busy", 503) from exc
        seen |= {q.id for q in questions}
        slots += [{"block": block, "subject": code, "question_id": q.id, "answer": None} for q in questions]
    now = utcnow()
    test = DtmTest(
        student_id=student.user_id, spec1=spec1, spec2=spec2, lang=lang, slots=slots,
        started_at=now, deadline_at=now + DURATION,
    )
    session.add(test)
    await session.commit()
    return test


async def get_owned(session: AsyncSession, student_id: int, test_id: int) -> DtmTest:
    test = await session.get(DtmTest, test_id)
    if test is None or test.student_id != student_id:
        raise DtmError("dtm_not_found", 404)
    if test.status == "active" and test.deadline_at <= utcnow():
        await finish(session, test)  # время вышло — завершаем с тем, что успел
    return test


async def answer(session: AsyncSession, student_id: int, test_id: int, slot: int, option: int | None) -> DtmTest:
    test = await get_owned(session, student_id, test_id)
    if test.status != "active":
        raise DtmError("dtm_finished", 409)
    if not 0 <= slot < len(test.slots):
        raise DtmError("bad_slot", 422)
    if option is not None and not 0 <= option <= 3:
        raise DtmError("bad_option", 422)
    slots = [dict(s) for s in test.slots]
    slots[slot]["answer"] = option  # None — снять ответ
    test.slots = slots
    await session.commit()
    return test


async def finish(session: AsyncSession, test: DtmTest) -> DtmTest:
    """Подсчёт: по блокам — верных ответов и баллов; итог — из 189."""
    if test.status == "finished":
        return test
    questions = {
        q.id: q for q in await session.scalars(select(DtmQuestion).where(DtmQuestion.id.in_([s["question_id"] for s in test.slots])))
    }
    weights = {block: weight for block, _code, _n, weight in plan(test.spec1, test.spec2)}
    results: dict[str, dict] = {}
    for slot in test.slots:
        q = questions.get(slot["question_id"])
        block = results.setdefault(slot["block"], {"subject": slot["subject"], "correct": 0, "total": 0, "points": 0.0})
        block["total"] += 1
        if q is not None and slot["answer"] == q.correct:
            block["correct"] += 1
            block["points"] = round(block["points"] + weights[slot["block"]], 1)
    test.results = results
    test.score = round(sum(b["points"] for b in results.values()), 1)
    test.status = "finished"
    test.finished_at = min(utcnow(), test.deadline_at)
    await session.commit()
    return test


async def recent(session: AsyncSession, student_id: int, limit: int = 20) -> list[DtmTest]:
    rows = await session.scalars(
        select(DtmTest).where(DtmTest.student_id == student_id).order_by(DtmTest.started_at.desc(), DtmTest.id.desc()).limit(limit)
    )
    return list(rows)


async def public(session: AsyncSession, test: DtmTest, lang: str) -> dict:
    """Во время теста — без правильных ответов; после — с ними и пояснениями для разбора."""
    finished = test.status == "finished"
    questions = {
        q.id: q for q in await session.scalars(select(DtmQuestion).where(DtmQuestion.id.in_([s["question_id"] for s in test.slots])))
    }
    items = []
    for i, slot in enumerate(test.slots):
        q = questions.get(slot["question_id"])
        item = {
            "n": i,
            "block": slot["block"],
            "subject": slot["subject"],
            "question": q.question if q else "",
            "options": q.options if q else [],
            "answer": slot["answer"],
        }
        if finished and q is not None:
            item.update(correct=q.correct, explanation=q.explanation)
        items.append(item)
    return {
        **brief(test, lang),
        "deadline_at": test.deadline_at.isoformat() + "Z",
        "seconds_left": max(0, int((test.deadline_at - utcnow()).total_seconds())) if not finished else 0,
        "questions": items,
        "results": test.results,
    }


def brief(test: DtmTest, lang: str) -> dict:
    return {
        "id": test.id,
        "status": test.status,
        "spec1": {"code": test.spec1, "name": SUBJECTS[test.spec1].name(lang)},
        "spec2": {"code": test.spec2, "name": SUBJECTS[test.spec2].name(lang)},
        "answered": sum(s["answer"] is not None for s in test.slots),
        "total": len(test.slots),
        "score": test.score,
        "max_score": MAX_SCORE,
        "started_at": test.started_at.isoformat() + "Z",
        "finished_at": test.finished_at.isoformat() + "Z" if test.finished_at else None,
    }


def subjects_view(lang: str) -> dict:
    return {
        "mandatory": [{"code": c, "name": SUBJECTS[c].name(lang)} for c in MANDATORY],
        "spec": [{"code": c, "name": SUBJECTS[c].name(lang)} for c in SPEC_CHOICES],
        "blocks": [{"block": b, "questions": n, "points": p} for b, n, p in BLOCKS],
        "minutes": int(DURATION.total_seconds() // 60),
        "max_score": MAX_SCORE,
        "min_grade": MIN_GRADE,
    }
