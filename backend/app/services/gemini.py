"""Объяснения через Google Gemini: запросы, парсинг и валидация JSON.

Шаг объяснения:
    {"title", "text", "example", "visual", "check_question", "options", "correct",
     "explanations"}
explanations — по одному пояснению на вариант: почему он верный или неверный
(бот показывает его после ответа). Может отсутствовать у старых тем.
visual — описание простой схемы, которую сайт рисует как SVG/карточки:
    {"type": "number_line"|"fractions"|"table"|"arrows"|"cards",
     "data": {...}, "caption": "…"}
"""
from __future__ import annotations

import json
import logging
import re
from typing import Protocol

from app.core.config import Settings, get_settings

log = logging.getLogger(__name__)

SUBJECTS = {
    "math": "математика",
    "russian": "русский язык",
    "uzbek": "узбекский язык (ona tili)",
    "english": "английский язык",
    "physics": "физика",
    "nature": "окружающий мир и биология",
    "history": "история",
    "other": "любой школьный предмет",
}

VISUAL_TYPES = ("number_line", "fractions", "table", "arrows", "cards")

SYSTEM_PROMPT = (
    "Ты добрый учитель для детей 10–13 лет. "
    "Объясняй тему простыми словами, короткими предложениями, с примерами из жизни ребёнка. "
    "Каждый шаг — одна мысль. Не используй сложные термины без пояснения. "
    "Не решай домашнее задание целиком — веди ученика к ответу. "
    "Отвечай только на учебные вопросы, на остальное вежливо возвращай к учёбе. "
    "Пиши на языке, который указан в задании. Возвращай строго JSON по схеме."
)

# На каком языке писать ВСЕ тексты JSON (ключи схемы остаются английскими)
LANGUAGE_RULES = {
    "ru": "Все тексты пиши по-русски.",
    "uz": (
        "Все тексты (title, text, example, caption, check_question, options, explanations, hint) "
        "пиши на узбекском языке латиницей (Oʻzbek lotin alifbosi), простыми словами для ребёнка."
    ),
    "en": (
        "Write all texts (title, text, example, caption, check_question, options, explanations, "
        "hint) in simple English for a child."
    ),
}


def language_rule(lang: str | None) -> str:
    return LANGUAGE_RULES.get(lang or "ru", LANGUAGE_RULES["ru"])

_STEP_SCHEMA = (
    '{"title": "…", "text": "…", "example": "…", '
    '"visual": {"type": "…", "data": {…}, "caption": "…"}, '
    '"check_question": "…", "options": ["…", "…", "…"], "correct": 0, '
    '"explanations": ["…", "…", "…"]}'
)

_VISUAL_GUIDE = (
    "visual — простая схема к шагу. Выбери ОДИН тип:\n"
    '- "number_line": {"min": 0, "max": 10, "marks": [{"value": 3, "label": "3"}], '
    '"highlight": [2, 5]} — числовая прямая (highlight — необязательный отрезок);\n'
    '- "fractions": {"items": [{"numerator": 1, "denominator": 4, "label": "1/4"}]} — '
    "дроби кружками (знаменатель до 12);\n"
    '- "table": {"headers": ["…"], "rows": [["…"]]} — маленькая таблица (до 5 строк);\n'
    '- "arrows": {"items": ["…", "…", "…"]} — цепочка действий стрелками (до 5);\n'
    '- "cards": {"items": [{"title": "…", "text": "…"}]} — 2–3 карточки.\n'
    "caption — одна короткая подпись к схеме."
)


class GeminiError(Exception):
    """Не удалось получить или разобрать ответ модели."""


class LessonProvider(Protocol):
    async def explain_topic(
        self,
        title: str,
        photo: bytes | None = None,
        photo_mime: str | None = None,
        subject: str | None = None,
        grade: int | None = None,
        lang: str = "ru",
    ) -> list[dict]: ...

    async def explain_step_simpler(
        self, title: str, step: dict, step_index: int, total_steps: int, lang: str = "ru"
    ) -> dict: ...

    async def make_practice(self, title: str, steps: list[dict], lang: str = "ru") -> list[dict]: ...

    async def verify_answers(self, items: list[dict]) -> list[dict]: ...


VERIFIER_PROMPT = (
    "Ты строгий проверяющий учитель. Тебе дают вопросы с вариантами ответа для ребёнка. "
    "Для каждого вопроса САМ реши его заново, не доверяя подсказкам, и укажи индекс верного "
    "варианта (с 0). Если верного варианта нет, их несколько или в пояснении есть фактическая "
    'ошибка — ok=false и коротко опиши проблему в issue. Верни строго JSON: '
    '{"results": [{"correct": 0, "ok": true, "issue": ""}]} — столько же элементов и в том же порядке.'
)


def validate_verdicts(data, items: list[dict]) -> list[dict] | None:
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        return None
    results = data["results"]
    if len(results) != len(items):
        return None
    clean = []
    for result, item in zip(results, items):
        if not isinstance(result, dict) or not isinstance(result.get("ok"), bool):
            return None
        if not _is_index(result.get("correct"), len(item["options"])):
            return None
        issue = result.get("issue") if isinstance(result.get("issue"), str) else ""
        clean.append({"ok": result["ok"], "correct": result["correct"], "issue": issue})
    return clean


# ---------- Разбор и валидация ----------

def extract_json(raw: str) -> dict:
    """Достаёт JSON из ответа: устойчив к ```json обёрткам и лишнему тексту."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
    raise GeminiError("Пустой ответ от модели")


def _is_index(value, size: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value < size


def _valid_options(options) -> bool:
    return (
        isinstance(options, list)
        and 2 <= len(options) <= 5
        and all(isinstance(o, str) and o.strip() for o in options)
    )


def normalize_visual(visual) -> dict | None:
    """Приводит visual к {"type", "data", "caption"}; неизвестное — в карточку."""
    if visual is None:
        return None
    if isinstance(visual, str):
        return {"type": "cards", "data": {"items": []}, "caption": visual.strip()} if visual.strip() else None
    if not isinstance(visual, dict):
        return None
    vtype = visual.get("type")
    data = visual.get("data") if isinstance(visual.get("data"), dict) else {}
    caption = visual.get("caption") if isinstance(visual.get("caption"), str) else ""
    if vtype not in VISUAL_TYPES:
        return {"type": "cards", "data": {"items": []}, "caption": caption} if caption else None
    return {"type": vtype, "data": data, "caption": caption}


def clean_explanations(value, size: int) -> list[str] | None:
    """Пояснения к вариантам: ровно по одному непустому на вариант, иначе — нет пояснений
    (урок из-за них не бракуем, бот тогда покажет запасной разбор)."""
    if not isinstance(value, list) or len(value) != size:
        return None
    if not all(isinstance(e, str) and e.strip() for e in value):
        return None
    return [e.strip() for e in value]


def validate_steps(data, min_steps: int, max_steps: int) -> list[dict] | None:
    if not isinstance(data, dict):
        return None
    steps = data.get("steps")
    if not isinstance(steps, list):
        # Модель иногда возвращает один шаг без обёртки {"steps": [...]}.
        if isinstance(data.get("title"), str) and isinstance(data.get("text"), str):
            steps = [data]
        else:
            return None
    if not (min_steps <= len(steps) <= max_steps):
        return None
    clean: list[dict] = []
    for step in steps:
        if not isinstance(step, dict):
            return None
        for key in ("title", "text", "example", "check_question"):
            if not isinstance(step.get(key), str) or not step[key].strip():
                return None
        if not _valid_options(step.get("options")):
            return None
        if not _is_index(step.get("correct"), len(step["options"])):
            return None
        clean.append(
            {
                "title": step["title"].strip(),
                "text": step["text"].strip(),
                "example": step["example"].strip(),
                "visual": normalize_visual(step.get("visual")),
                "check_question": step["check_question"].strip(),
                "options": [o.strip() for o in step["options"]],
                "correct": step["correct"],
                "explanations": clean_explanations(step.get("explanations"), len(step["options"])),
            }
        )
    return clean


def validate_practice(data) -> list[dict] | None:
    if not isinstance(data, dict):
        return None
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 3:
        return None
    clean = []
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("question"), str):
            return None
        if not _valid_options(task.get("options")):
            return None
        if not _is_index(task.get("correct"), len(task["options"])):
            return None
        hint = task.get("hint") if isinstance(task.get("hint"), str) else ""
        clean.append(
            {
                "question": task["question"].strip(),
                "options": [o.strip() for o in task["options"]],
                "correct": task["correct"],
                "hint": hint.strip(),
            }
        )
    return clean


def public_step(step: dict) -> dict:
    """Шаг без служебных полей (для повторной отправки модели)."""
    return {k: v for k, v in step.items() if k not in ("simpler",)}


# ---------- Клиент Gemini ----------

class LessonService:
    """Обмен с Gemini. При ошибке сети/JSON — повторный запрос (до 2 попыток)."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        from google import genai
        from google.genai import types

        self._types = types
        self.client = genai.Client(api_key=self.settings.gemini_api_key)
        self._model = self.settings.gemini_model

    async def explain_topic(
        self,
        title: str,
        photo: bytes | None = None,
        photo_mime: str | None = None,
        subject: str | None = None,
        grade: int | None = None,
        lang: str = "ru",
    ) -> list[dict]:
        context = []
        if subject:
            context.append(f"Предмет: {SUBJECTS.get(subject, subject)}.")
        if grade:
            context.append(f"Класс: {grade}. Подстрой сложность под этот класс.")
        photo_hint = (
            "К сообщению приложено фото задания — сначала пойми, о какой теме задание, "
            "и объясни именно эту тему, не решая задание целиком.\n"
            if photo
            else ""
        )
        prompt = (
            f"Ученик написал: «{title}». {' '.join(context)}\n"
            f"{photo_hint}"
            "Объясни эту тему по шагам.\n"
            f'Схема ответа: {{"steps": [{_STEP_SCHEMA}]}}\n'
            f"{_VISUAL_GUIDE}\n"
            "Требования: 3–5 шагов. Каждый шаг — одна мысль, 1–3 коротких предложения, "
            "пример из жизни ребёнка. check_question — мини-вопрос по этому шагу, "
            "options — 3–4 коротких варианта, correct — индекс верного варианта (с 0). "
            "explanations — по одному пояснению на КАЖДЫЙ вариант, в том же порядке: "
            "1–2 коротких предложения, почему этот вариант верный или почему неверный.\n"
            f"{language_rule(lang)}"
        )
        return await self._ask(
            prompt, photo, photo_mime, lambda d: validate_steps(d, 3, 5), "объяснение"
        )

    async def explain_step_simpler(
        self, title: str, step: dict, step_index: int, total_steps: int, lang: str = "ru"
    ) -> dict:
        prompt = (
            f"Ученик ошибся на шаге {step_index + 1} из {total_steps} по теме «{title}».\n"
            f"Вот этот шаг: {json.dumps(public_step(step), ensure_ascii=False)}\n"
            "Объясни этот же шаг ещё проще: короче, медленнее, с самой простой "
            "аналогией из жизни ребёнка. Можно выбрать другую схему visual, если она нагляднее.\n"
            f'Схема ответа: {{"steps": [{_STEP_SCHEMA}]}} — ровно ОДИН шаг.\n'
            f"{_VISUAL_GUIDE}\n"
            "check_question и options оставь ровно такими же, correct — той же цифрой.\n"
            f"{language_rule(lang)}"
        )
        steps = await self._ask(
            prompt, None, None, lambda d: validate_steps(d, 1, 1), "упрощение"
        )
        return steps[0]

    async def make_practice(self, title: str, steps: list[dict], lang: str = "ru") -> list[dict]:
        summary = "; ".join(s.get("title", "") for s in steps)
        prompt = (
            f"Ученик только что разобрал тему «{title}» (шаги: {summary}).\n"
            "Дай ровно 3 коротких задачи для закрепления, от простой к чуть сложнее. "
            "Каждая — с 3–4 вариантами ответа и подсказкой на случай ошибки.\n"
            f"{language_rule(lang)}\n"
            'Схема ответа: {"tasks": [{"question": "…", "options": ["…", "…", "…"], '
            '"correct": 0, "hint": "…"}]}'
        )
        return await self._ask(prompt, None, None, validate_practice, "задачи")

    async def verify_answers(self, items: list[dict]) -> list[dict]:
        """Независимая проверка: items = [{"question", "options", "correct", "context"}]."""
        payload = [
            {
                "n": i,
                "context": item.get("context", ""),
                "question": item["question"],
                "options": item["options"],
                "marked_correct": item["correct"],
            }
            for i, item in enumerate(items)
        ]
        prompt = f"Вопросы:\n{json.dumps(payload, ensure_ascii=False)}"
        return await self._ask(
            prompt,
            None,
            None,
            lambda d: validate_verdicts(d, items),
            "проверка",
            system=VERIFIER_PROMPT,
            temperature=0.0,
        )

    async def _ask(
        self,
        prompt,
        photo,
        photo_mime,
        validator,
        what: str,
        system: str = SYSTEM_PROMPT,
        temperature: float = 0.5,
    ):
        last_error: Exception | None = None
        for _ in range(2):
            try:
                raw = await self._generate(prompt, photo, photo_mime, system, temperature)
                result = validator(extract_json(raw))
                if result:
                    return result
                raise GeminiError("Ответ не прошёл валидацию схемы")
            except Exception as exc:  # сеть, API, JSON
                log.warning("Gemini (%s): %s", what, exc)
                last_error = exc
        raise GeminiError(f"Не удалось получить {what}: {last_error}")

    async def _generate(
        self,
        prompt: str,
        photo: bytes | None,
        photo_mime: str | None,
        system: str = SYSTEM_PROMPT,
        temperature: float = 0.5,
    ) -> str:
        parts: list = [prompt]
        if photo:
            parts.append(
                self._types.Part.from_bytes(data=photo, mime_type=photo_mime or "image/jpeg")
            )
        try:
            response = await self.client.aio.models.generate_content(
                model=self._model,
                contents=parts,
                config=self._types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    temperature=temperature,
                ),
            )
        except Exception:
            # Фоллбек без response_mime_type (некоторые модели его не принимают).
            response = await self.client.aio.models.generate_content(
                model=self._model,
                contents=parts,
                config=self._types.GenerateContentConfig(
                    system_instruction=system, temperature=temperature
                ),
            )
        if not response.text:
            raise GeminiError("Пустой ответ от модели")
        return response.text


def make_lesson_provider(settings: Settings | None = None) -> LessonProvider:
    """Настоящий Gemini, либо заглушка при GEMINI_FAKE=1 / без ключа."""
    settings = settings or get_settings()
    if settings.gemini_fake or not settings.gemini_api_key:
        from app.services.gemini_stub import StubLessonService

        log.warning("Gemini отключён: используется демо-заглушка объяснений")
        return StubLessonService()
    return LessonService(settings)
