"""Банк вопросов вечернего теста (Модуль 4).

Вопросы по теме программы и сложности (1 — просто, 2 — средне, 3 — сложно)
генерируются ИИ ОДИН раз и хранятся в question_bank: следующий ученик получает
их без запроса к модели (лимит расходов на ИИ). Каждый вопрос независимо
перепроверяется вторым запросом (как объяснения) — ошибочные не попадают в банк.
"""
from __future__ import annotations

import json
import logging
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import BankQuestion, CurriculumSubject, CurriculumTopic
from app.services.gemini import VERIFIER_PROMPT, GeminiError, extract_json, language_rule, validate_verdicts

log = logging.getLogger(__name__)

BATCH = 4  # вопросов за один запрос к модели
DIFFICULTY_TEXT = {
    1: "простой: одно действие, базовое определение",
    2: "средний: два действия или применение правила",
    3: "сложный: несколько шагов, типичная ловушка",
}


class QuestionGenerator(Protocol):
    async def generate(self, topic: str, subject: str, grade: int, difficulty: int, lang: str) -> list[dict]: ...


def validate_questions(data) -> list[dict]:
    items = data.get("questions") if isinstance(data, dict) else None
    clean = []
    for q in items or []:
        if not isinstance(q, dict):
            continue
        question, options, correct = q.get("question"), q.get("options"), q.get("correct")
        explanation = q.get("explanation") if isinstance(q.get("explanation"), str) else ""
        if not isinstance(question, str) or not question.strip():
            continue
        if not isinstance(options, list) or not 3 <= len(options) <= 4 or not all(isinstance(o, str) and o.strip() for o in options):
            continue
        if len({o.strip() for o in options}) != len(options):
            continue  # одинаковые варианты
        if not isinstance(correct, int) or isinstance(correct, bool) or not 0 <= correct < len(options):
            continue
        clean.append({
            "question": question.strip()[:1000],
            "options": [o.strip()[:200] for o in options],
            "correct": correct,
            "explanation": explanation.strip()[:1000],
        })
    return clean


class GeminiQuestionGenerator:
    def __init__(self, settings: Settings):
        from google import genai
        from google.genai import types

        self._types = types
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.gemini_model

    async def _json(self, prompt: str, system: str, temperature: float) -> dict:
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=[prompt],
            config=self._types.GenerateContentConfig(system_instruction=system, response_mime_type="application/json", temperature=temperature),
        )
        return extract_json(response.text or "")

    async def generate(self, topic, subject, grade, difficulty, lang) -> list[dict]:
        prompt = (
            f"Предмет: {subject}, {grade} класс. Тема программы: «{topic}».\n"
            f"Составь {BATCH} разных вопроса для короткого вечернего теста. Сложность — {DIFFICULTY_TEXT[difficulty]}.\n"
            "У каждого 3–4 коротких варианта ответа, ровно один верный (correct — индекс с 0), "
            "explanation — 1–2 предложения, почему верный ответ верный (ученик увидит после ошибки).\n"
            f"{language_rule(lang)}\n"
            'Схема: {"questions": [{"question": "…", "options": ["…", "…", "…"], "correct": 0, "explanation": "…"}]}'
        )
        system = "Ты составляешь проверочные вопросы для школьников по программе Узбекистана. Возвращай строго JSON."
        try:
            questions = validate_questions(await self._json(prompt, system, 0.6))
            if not questions:
                raise GeminiError("Пустой набор вопросов")
            # Независимая перепроверка ответов (температура 0): спорные вопросы отбрасываем
            payload = [{"n": i, "context": topic, "question": q["question"], "options": q["options"], "marked_correct": q["correct"]}
                       for i, q in enumerate(questions)]
            verdicts = validate_verdicts(await self._json(f"Вопросы:\n{json.dumps(payload, ensure_ascii=False)}", VERIFIER_PROMPT, 0.0), questions)
        except Exception as exc:
            raise GeminiError(f"Вопросы не сгенерированы: {exc}") from exc
        if verdicts is None:
            raise GeminiError("Проверка вопросов не прошла")
        return [q for q, v in zip(questions, verdicts) if v["ok"] and v["correct"] == q["correct"]]


class StubQuestionGenerator:
    """Без модели: корректные арифметические вопросы нужной сложности — для демо и тестов."""

    def __init__(self):
        self.calls = 0

    async def generate(self, topic, subject, grade, difficulty, lang) -> list[dict]:
        self.calls += 1
        out = []
        for i in range(BATCH):
            a, b = (3 + i) * difficulty, (2 + i) * difficulty + self.calls
            right = a + b if difficulty < 3 else a * b
            sign = "+" if difficulty < 3 else "×"
            options = [str(right), str(right + 1), str(right - 1)]
            shift = (i + self.calls) % 3  # верный ответ — не всегда первый
            options = options[shift:] + options[:shift]
            out.append({
                "question": f"«{topic}»: {a} {sign} {b} = ?",
                "options": options,
                "correct": options.index(str(right)),
                "explanation": f"{a} {sign} {b} = {right}",
            })
        return out


def make_question_generator(settings: Settings | None = None) -> QuestionGenerator:
    settings = settings or get_settings()
    if settings.gemini_fake or not settings.gemini_api_key:
        return StubQuestionGenerator()
    return GeminiQuestionGenerator(settings)


async def pick_question(
    session: AsyncSession,
    generator: QuestionGenerator,
    topic: CurriculumTopic,
    difficulty: int,
    lang: str,
    exclude: set[int],
) -> BankQuestion | None:
    """Вопрос из банка, который ученик ещё не видел; нет такого — генерируем пачку."""
    stmt = (
        select(BankQuestion)
        .where(BankQuestion.topic_id == topic.id, BankQuestion.difficulty == difficulty, BankQuestion.lang == lang)
        .order_by(BankQuestion.id)
    )
    bank = list(await session.scalars(stmt))
    fresh = [q for q in bank if q.id not in exclude]
    if fresh:
        return fresh[0]
    subject = await session.get(CurriculumSubject, topic.subject_id)
    try:
        generated = await generator.generate(
            topic.name(lang), subject.name_ru if subject else "", topic.grade, difficulty, lang
        )
    except GeminiError as exc:
        log.warning("Банк вопросов (тема %s, сложность %s): %s", topic.id, difficulty, exc)
        generated = []
    for q in generated:
        session.add(BankQuestion(topic_id=topic.id, difficulty=difficulty, lang=lang, **q))
    await session.flush()
    bank = list(await session.scalars(stmt))
    fresh = [q for q in bank if q.id not in exclude]
    return fresh[0] if fresh else (bank[0] if bank else None)  # все видел — лучше повтор, чем пусто
