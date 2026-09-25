"""Проверка рукописной работы Vision-моделью (Модуль 5.1, шаги 2–4 конвейера).

Модель распознаёт текст и формулы (узбекский латиницей и кириллицей, русский,
английский), сверяет с заданием и ключом и возвращает ПРЕДЛОЖЕНИЕ: оценку,
пометки ошибок с координатами, комментарий ученику и уверенность 0–100.
Итоговую оценку всегда ставит учитель.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings, get_settings
from app.services.gemini import SUBJECTS, GeminiError, extract_json, language_rule

log = logging.getLogger(__name__)

MARK_TYPES = ("calculation", "formula", "logic", "spelling", "other")


@dataclass
class CheckTask:
    task_text: str | None
    answer_key: str | None
    max_score: int
    subject: str | None
    grade: int | None
    lang: str = "ru"  # язык комментария ученику


class WorkChecker(Protocol):
    async def check_work(self, file: bytes, mime: str, task: CheckTask) -> dict: ...


SYSTEM_PROMPT = (
    "Ты — помощник учителя. Проверяешь рукописную работу школьника по фото. "
    "Ты НЕ ставишь окончательную оценку: ты предлагаешь её учителю и честно оцениваешь, "
    "насколько уверен. Если почерк неразборчив, фото размыто или работа не относится к "
    "заданию — снижай confidence, не выдумывай текст. Распознавай узбекский (латиница и "
    "кириллица), русский и английский, а также математические записи. "
    "Возвращай строго JSON по схеме."
)

SCHEMA = (
    '{"recognized_text": "…", "score": 4, "confidence": 85, "neatness": 70, '
    '"comment": "…", "marks": [{"box": [0.1, 0.2, 0.3, 0.05], '
    '"type": "calculation", "note": "…"}]}'
)


def _clamp01(value) -> float | None:
    return max(0.0, min(1.0, float(value))) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def validate_result(data, max_score: int) -> dict | None:
    """Строгая проверка ответа модели; координаты — доли от размеров фото (0–1)."""
    if not isinstance(data, dict):
        return None
    score, confidence = data.get("score"), data.get("confidence")
    if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= max_score:
        return None
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        return None
    text = data.get("recognized_text") if isinstance(data.get("recognized_text"), str) else ""
    comment = data.get("comment") if isinstance(data.get("comment"), str) else ""
    neatness = data.get("neatness")
    neatness = int(max(0, min(100, neatness))) if isinstance(neatness, (int, float)) and not isinstance(neatness, bool) else None
    marks = []
    for mark in data.get("marks") or []:
        if not isinstance(mark, dict) or not isinstance(mark.get("box"), list) or len(mark["box"]) != 4:
            continue
        box = [_clamp01(v) for v in mark["box"]]
        if None in box or box[2] <= 0 or box[3] <= 0:
            continue
        x, y, w, h = box
        marks.append(
            {
                "box": [round(x, 4), round(y, 4), round(min(w, 1 - x), 4), round(min(h, 1 - y), 4)],
                "type": mark.get("type") if mark.get("type") in MARK_TYPES else "other",
                "note": str(mark.get("note") or "")[:300],
            }
        )
    confidence = int(max(0, min(100, confidence)))
    if not text.strip():
        confidence = min(confidence, 40)  # ничего не распознано — уверенности быть не может
    return {
        "recognized_text": text.strip()[:8000],
        "score": score,
        "confidence": confidence,
        "neatness": neatness,
        "comment": comment.strip()[:2000],
        "marks": marks[:30],
    }


def build_prompt(task: CheckTask) -> str:
    parts = []
    if task.subject:
        parts.append(f"Предмет: {SUBJECTS.get(task.subject, task.subject)}.")
    if task.grade:
        parts.append(f"Класс: {task.grade}.")
    parts.append(f"Задание: {task.task_text or 'не указано — определи по работе'}.")
    if task.answer_key:
        parts.append(f"Ключ ответов учителя: {task.answer_key}.")
    return (
        " ".join(parts) + "\n"
        f"Оцени работу по шкале от 0 до {task.max_score} (целое число).\n"
        "Найди ошибки: в вычислениях (calculation), формулах (formula), логике решения "
        "(logic), орфографии (spelling). Для каждой ошибки укажи прямоугольник box = "
        "[x, y, ширина, высота] в долях от размеров изображения (0–1) и короткое пояснение.\n"
        "neatness — аккуратность оформления 0–100. comment — 1–3 доброжелательных предложения "
        "ученику: что получилось и что исправить. confidence — насколько ты уверен в оценке "
        "и распознавании (0–100).\n"
        f"Комментарий пиши так: {language_rule(task.lang)}\n"
        f"Схема ответа: {SCHEMA}"
    )


class GeminiWorkChecker:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        from google import genai
        from google.genai import types

        self._types = types
        self.client = genai.Client(api_key=self.settings.gemini_api_key)

    async def check_work(self, file: bytes, mime: str, task: CheckTask) -> dict:
        prompt = build_prompt(task)
        last: Exception | None = None
        for _ in range(2):
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.settings.gemini_model,
                    contents=[prompt, self._types.Part.from_bytes(data=file, mime_type=mime)],
                    config=self._types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        temperature=0.0,  # проверка — не творчество
                    ),
                )
                result = validate_result(extract_json(response.text or ""), task.max_score)
                if result:
                    return result
                raise GeminiError("Ответ проверки не прошёл валидацию")
            except Exception as exc:
                log.warning("Vision-проверка: %s", exc)
                last = exc
        raise GeminiError(f"Не удалось проверить работу: {last}")


class StubWorkChecker:
    """Детерминированная заглушка: по содержимому файла выбирает один из трёх случаев
    уверенности (95 / 80 / 55) — удобно для демо и тестов правил подтверждения."""

    def __init__(self):
        self.fail_next = False
        self.calls = 0

    async def check_work(self, file: bytes, mime: str, task: CheckTask) -> dict:
        self.calls += 1
        if self.fail_next:
            self.fail_next = False
            raise GeminiError("Сбой модели (заглушка)")
        n = int(hashlib.sha256(file).hexdigest(), 16)
        confidence = (95, 80, 55)[n % 3]
        score = max(0, task.max_score - n % 2)
        return validate_result(
            {
                "recognized_text": "S = (a + b) / 2 · h = (10 + 6) / 2 · 4 = 32",
                "score": score,
                "confidence": confidence,
                "neatness": 60 + n % 40,
                "comment": "Решение верное, запиши единицы измерения в ответе."
                if score == task.max_score
                else "Проверь вычисление во второй строке.",
                "marks": [] if score == task.max_score else [
                    {"box": [0.12, 0.40, 0.55, 0.08], "type": "calculation", "note": "(10 + 6) / 2 = 8, а не 9"}
                ],
            },
            task.max_score,
        )


def make_work_checker(settings: Settings | None = None) -> WorkChecker:
    settings = settings or get_settings()
    if settings.gemini_fake or not settings.gemini_api_key:
        log.warning("Vision-проверка работ: демо-заглушка (нет ключа Gemini)")
        return StubWorkChecker()
    return GeminiWorkChecker(settings)
