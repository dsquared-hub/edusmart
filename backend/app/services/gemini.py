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

    async def make_stories(
        self, title: str, subject: str | None = None, grade: int | None = None, lang: str = "ru"
    ) -> list[dict]: ...

    async def tutor_turn(
        self,
        problem: str,
        history: list[dict],
        photo: bytes | None = None,
        photo_mime: str | None = None,
        subject: str | None = None,
        grade: int | None = None,
        lang: str = "ru",
    ) -> dict: ...

    async def tutor_check(self, problem: str, history: list[dict], turn: dict) -> dict: ...

    async def ielts_writing_prompt(self, task: int) -> dict: ...

    async def ielts_grade_writing(self, task: int, prompt: str, essay: str, words: int, examiner: str) -> dict: ...

    async def ielts_test_material(self, kind: str) -> dict: ...

    async def ielts_speaking_material(self) -> dict: ...

    async def ielts_speaking_turn(self, part: int, question: str, audio: bytes, mime: str) -> dict: ...

    async def ielts_grade_speaking(self, turns: list[dict], examiner: str) -> dict: ...


# ---------- IELTS Speaking ----------

IELTS_CRITERIA_SPEAKING = ("FC", "LR", "GRA", "P")  # Fluency & Coherence, Lexical, Grammar, Pronunciation

IELTS_SPEAKING_EXAMINER = (
    "You are a certified IELTS Speaking examiner and a kind coach for a 16-year-old Uzbek student. "
    "You hear the student's recorded answer. Transcribe it faithfully (keep the student's mistakes, do not correct "
    "the transcript). Then point out the most important grammar and vocabulary mistakes (quote the exact words from "
    "your transcript) and pronunciation problems you actually heard (the word and a simple tip). Return strict JSON."
)


def _strs(items, keys: tuple[str, ...], limit: int) -> list[dict]:
    out = []
    for item in items or []:
        if isinstance(item, dict) and all(isinstance(item.get(k), str) and item[k].strip() for k in keys[:1]):
            out.append({k: (item.get(k) if isinstance(item.get(k), str) else "").strip()[:300] for k in keys})
    return out[:limit]


def validate_speaking_material(data) -> dict | None:
    if not isinstance(data, dict):
        return None
    part1 = [q.strip() for q in data.get("part1") or [] if isinstance(q, str) and q.strip()]
    part3 = [q.strip() for q in data.get("part3") or [] if isinstance(q, str) and q.strip()]
    card = data.get("part2")
    if len(part1) < 4 or len(part3) < 4 or not isinstance(card, dict) or not isinstance(card.get("topic"), str):
        return None
    points = [p.strip() for p in card.get("points") or [] if isinstance(p, str) and p.strip()]
    if not 3 <= len(points) <= 4:
        return None
    theme = data.get("theme") if isinstance(data.get("theme"), str) else ""
    return {
        "theme": theme.strip()[:120],
        "part1": part1[:4],
        "part2": {"topic": card["topic"].strip()[:200], "points": points},
        "part3": part3[:4],
    }


def validate_speaking_turn(data) -> dict | None:
    if not isinstance(data, dict) or not isinstance(data.get("transcript"), str):
        return None
    comment = data.get("comment") if isinstance(data.get("comment"), str) else ""
    return {
        "transcript": data["transcript"].strip()[:4000],
        "grammar": _strs(data.get("grammar"), ("quote", "fix", "explanation"), 8),
        "vocabulary": _strs(data.get("vocabulary"), ("quote", "better"), 6),
        "pronunciation": _strs(data.get("pronunciation"), ("word", "tip"), 6),
        "comment": comment.strip()[:500],
    }


def validate_speaking_grade(data) -> dict | None:
    if not isinstance(data, dict) or not isinstance(data.get("criteria"), dict):
        return None
    criteria = {}
    for key in IELTS_CRITERIA_SPEAKING:
        item = data["criteria"].get(key)
        band = _band(item.get("band")) if isinstance(item, dict) else None
        if band is None:
            return None
        comment = item.get("comment") if isinstance(item.get("comment"), str) else ""
        criteria[key] = {"band": band, "comment": comment.strip()[:600]}
    summary = data.get("summary") if isinstance(data.get("summary"), str) else ""
    return {"criteria": criteria, "summary": summary.strip()[:1200]}


# ---------- IELTS Reading / Listening ----------

IELTS_QUESTION_TYPES = ("mcq", "tfng", "gap")
TFNG = ("TRUE", "FALSE", "NOT GIVEN")
IELTS_MIN_QUESTIONS = 10


def normalize_answer(value: str) -> str:
    """Ответ «впиши слово»: регистр, пробелы и знаки по краям не важны."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s'’%-]", " ", value.lower())).strip()


def validate_ielts_test(data, kind: str) -> dict | None:
    """Reading: {title, passage, questions}; Listening: {title, context, script: [{speaker, text}], questions}."""
    if not isinstance(data, dict) or not isinstance(data.get("title"), str):
        return None
    out: dict = {"kind": kind, "title": data["title"].strip()[:200]}
    if kind == "reading":
        passage = data.get("passage")
        if not isinstance(passage, str) or not 1500 <= len(passage) <= 9000:
            return None
        out["passage"] = passage.strip()
    else:
        script = []
        for line in data.get("script") or []:
            if isinstance(line, dict) and isinstance(line.get("text"), str) and line["text"].strip():
                speaker = line.get("speaker") if isinstance(line.get("speaker"), str) else "A"
                script.append({"speaker": speaker.strip()[:30] or "A", "text": line["text"].strip()[:600]})
        if not 6 <= len(script) <= 60:
            return None
        context = data.get("context") if isinstance(data.get("context"), str) else ""
        out.update(context=context.strip()[:300], script=script)
    questions = []
    for q in data.get("questions") or []:
        if not isinstance(q, dict) or q.get("type") not in IELTS_QUESTION_TYPES or not isinstance(q.get("text"), str):
            continue
        evidence = q.get("evidence") if isinstance(q.get("evidence"), str) else ""
        item = {"type": q["type"], "text": q["text"].strip()[:500], "evidence": evidence.strip()[:400]}
        if q["type"] == "mcq":
            if not _valid_options(q.get("options")) or not _is_index(q.get("answer"), len(q["options"])):
                continue
            item.update(options=[o.strip()[:200] for o in q["options"]], answer=q["answer"])
        elif q["type"] == "tfng":
            if kind != "reading" or q.get("answer") not in TFNG:
                continue
            item["answer"] = q["answer"]
        else:
            answer = q.get("answer")
            if not isinstance(answer, str) or not answer.strip() or len(answer.split()) > 3 or "____" not in item["text"]:
                continue
            alts = [a.strip() for a in q.get("alternatives") or [] if isinstance(a, str) and a.strip()]
            item.update(answer=answer.strip(), alternatives=alts[:4])
        questions.append(item)
    if len(questions) < IELTS_MIN_QUESTIONS:
        return None
    out["questions"] = questions[:14]
    return out


def ielts_answer_ok(question: dict, given) -> bool:
    """Код проверяет ответ ученика (и ответ проверяющей модели) — модели тут не доверяем."""
    if question["type"] == "mcq":
        return isinstance(given, int) and not isinstance(given, bool) and given == question["answer"]
    if question["type"] == "tfng":
        return isinstance(given, str) and given.strip().upper() == question["answer"]
    if not isinstance(given, str):
        return False
    accepted = {normalize_answer(a) for a in [question["answer"], *question.get("alternatives", [])]}
    return normalize_answer(given) in accepted


IELTS_TEST_PROMPT = (
    "You write IELTS practice tests for Uzbek high-school students (grades 10–11). Match the real exam in style "
    "and difficulty (Band 5–7 level). Every answer must be clearly supported by the text. For each question give "
    "\"evidence\": the exact sentence from the text that contains the answer. Return strict JSON."
)


# ---------- IELTS Writing ----------

IELTS_CRITERIA_WRITING = ("TR", "CC", "LR", "GRA")  # Task Response/Achievement, Coherence, Lexical, Grammar
IELTS_ERROR_TYPES = ("grammar", "vocabulary", "spelling", "punctuation", "style")
IELTS_CHART_TYPES = ("bar", "line", "pie", "table")

IELTS_WRITING_TASK_PROMPT = (
    "You write IELTS Academic Writing tasks for Uzbek high-school students (grades 10–11) preparing for IELTS. "
    "Tasks must look exactly like real IELTS tasks, with realistic, internally consistent data. Return strict JSON."
)

IELTS_EXAMINER_PROMPT = (
    "You are a certified IELTS Writing examiner. Grade strictly by the official public band descriptors "
    "(Task Achievement for Task 1 / Task Response for Task 2, Coherence and Cohesion, Lexical Resource, "
    "Grammatical Range and Accuracy). Bands are 0–9 in steps of 0.5. Be fair and calibrated — do not inflate. "
    "Under-length answers are penalised in TR as in the real exam. For errors, quote the EXACT words from the essay "
    "(copy them character by character) and give the correction. Write comments and explanations in simple "
    "English a 16-year-old understands. Return strict JSON."
)


def _band(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 9:
        return None
    return round(float(value) * 2) / 2


def _numbers(values, size: int) -> list[float] | None:
    if not isinstance(values, list) or len(values) != size:
        return None
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        return None
    return [float(v) for v in values]


def validate_writing_prompt(data, task: int) -> dict | None:
    if not isinstance(data, dict):
        return None
    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not 30 <= len(prompt.strip()) <= 1500:
        return None
    out: dict = {"task": task, "prompt": prompt.strip()}
    if task == 2:
        return out
    chart = data.get("chart")
    if not isinstance(chart, dict) or chart.get("type") not in IELTS_CHART_TYPES:
        return None
    labels = chart.get("labels")
    if not isinstance(labels, list) or not 2 <= len(labels) <= 12 or not all(isinstance(x, str) and x.strip() for x in labels):
        return None
    series = []
    for s in chart.get("series") or []:
        if not isinstance(s, dict) or not isinstance(s.get("name"), str):
            return None
        values = _numbers(s.get("values"), len(labels))
        if values is None:
            return None
        series.append({"name": s["name"].strip()[:60], "values": values})
    if not 1 <= len(series) <= 4 or (chart["type"] == "pie" and (len(series) != 1 or min(series[0]["values"]) < 0)):
        return None
    title = chart.get("title") if isinstance(chart.get("title"), str) else ""
    unit = chart.get("unit") if isinstance(chart.get("unit"), str) else ""
    out["chart"] = {
        "type": chart["type"], "title": title.strip()[:200], "unit": unit.strip()[:30],
        "labels": [x.strip()[:40] for x in labels], "series": series,
    }
    return out


def validate_writing_grade(data) -> dict | None:
    if not isinstance(data, dict) or not isinstance(data.get("criteria"), dict):
        return None
    criteria = {}
    for key in IELTS_CRITERIA_WRITING:
        item = data["criteria"].get(key)
        band = _band(item.get("band")) if isinstance(item, dict) else None
        if band is None:
            return None
        comment = item.get("comment") if isinstance(item.get("comment"), str) else ""
        criteria[key] = {"band": band, "comment": comment.strip()[:800]}
    errors = []
    for e in data.get("errors") or []:
        if not isinstance(e, dict) or not isinstance(e.get("quote"), str) or not e["quote"].strip():
            continue
        kind = e.get("type") if e.get("type") in IELTS_ERROR_TYPES else "grammar"
        fix = e.get("fix") if isinstance(e.get("fix"), str) else ""
        why = e.get("explanation") if isinstance(e.get("explanation"), str) else ""
        errors.append({"quote": e["quote"].strip()[:300], "type": kind, "fix": fix.strip()[:300], "explanation": why.strip()[:400]})
    summary = data.get("summary") if isinstance(data.get("summary"), str) else ""
    improved = data.get("improved") if isinstance(data.get("improved"), str) else ""
    return {"criteria": criteria, "errors": errors[:25], "summary": summary.strip()[:1200], "improved": improved.strip()[:2500]}


TUTOR_PROMPT = (
    "Ты — сократовский репетитор для школьника 10–17 лет. ГЛАВНОЕ ПРАВИЛО: никогда не давай "
    "готовый ответ и не решай задачу за ученика — ни целиком, ни последний шаг. Разбей решение "
    "на 2–3 наводящих вопроса и задавай их по одному. На каждый ответ ученика: коротко скажи, "
    "что верно, мягко укажи на ошибку и задай следующий наводящий вопрос или дай маленькую "
    "подсказку. Когда ученик САМ назвал верный итоговый ответ — похвали, коротко подведи итог "
    "и поставь solved=true. Отвечай 1–3 короткими предложениями. Не уходи от учёбы. "
    "Возвращай строго JSON."
)

TUTOR_CHECK_PROMPT = (
    "Ты проверяешь ответ сократовского репетитора школьнику. Реши задачу сам. Нарушение "
    "(ok=false), если реплика репетитора: 1) называет итоговый ответ или решает последний шаг "
    "за ученика; 2) содержит фактическую или вычислительную ошибку; 3) ставит solved=true, хотя "
    "ученик ещё НЕ назвал верный итоговый ответ сам; 4) ставит solved=false, хотя ученик уже "
    'назвал верный итоговый ответ. Верни строго JSON: {"ok": true, "issue": ""}.'
)

TUTOR_MAX_REPLY = 600


def validate_tutor_turn(data, need_problem: bool) -> dict | None:
    if not isinstance(data, dict):
        return None
    reply = data.get("reply")
    if not isinstance(reply, str) or not reply.strip() or len(reply) > TUTOR_MAX_REPLY * 2:
        return None
    solved = data.get("solved", False)
    if not isinstance(solved, bool):
        return None
    out = {"reply": reply.strip()[:TUTOR_MAX_REPLY], "solved": solved}
    if need_problem:
        problem = data.get("problem")
        if not isinstance(problem, str) or not problem.strip():
            return None
        out["problem"] = problem.strip()[:1500]
    return out


def validate_tutor_check(data) -> dict | None:
    if not isinstance(data, dict) or not isinstance(data.get("ok"), bool):
        return None
    issue = data.get("issue") if isinstance(data.get("issue"), str) else ""
    return {"ok": data["ok"], "issue": issue}


def tutor_transcript(history: list[dict]) -> str:
    """Диалог для модели: только роли и тексты — без имён и идентификаторов ученика."""
    who = {"student": "Ученик", "tutor": "Репетитор"}
    return "\n".join(f"{who.get(m['role'], m['role'])}: {m['text']}" for m in history)


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


STORY_MIN_SLIDES, STORY_MAX_SLIDES = 6, 10
STORY_MAX_WORDS = 30  # просим до 20 слов; с запасом, чтобы не браковать из-за пары слов
STORY_MIN_QUESTIONS, STORY_MAX_QUESTIONS = 2, 4


def validate_stories(data) -> list[dict] | None:
    """Stories: 6–10 карточек по ≤ ~20 слов, на 2–4 из них — мини-вопрос."""
    if not isinstance(data, dict) or not isinstance(data.get("slides"), list):
        return None
    slides = data["slides"]
    if not STORY_MIN_SLIDES <= len(slides) <= STORY_MAX_SLIDES:
        return None
    clean = []
    for slide in slides:
        if not isinstance(slide, dict):
            return None
        title, text = slide.get("title"), slide.get("text")
        if not isinstance(title, str) or not title.strip() or not isinstance(text, str) or not text.strip():
            return None
        if len(text.split()) > STORY_MAX_WORDS:
            return None
        emoji = slide.get("emoji") if isinstance(slide.get("emoji"), str) else ""
        item = {"emoji": emoji.strip()[:8], "title": title.strip()[:120], "text": text.strip()}
        question = slide.get("question")
        if isinstance(question, str) and question.strip():
            if not _valid_options(slide.get("options")) or not _is_index(slide.get("correct"), len(slide["options"])):
                return None
            explanation = slide.get("explanation") if isinstance(slide.get("explanation"), str) else ""
            item.update(
                question=question.strip(),
                options=[o.strip() for o in slide["options"]],
                correct=slide["correct"],
                explanation=explanation.strip(),
            )
        clean.append(item)
    questions = sum("question" in item for item in clean)
    if not STORY_MIN_QUESTIONS <= questions <= STORY_MAX_QUESTIONS:
        return None
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

    async def make_stories(
        self, title: str, subject: str | None = None, grade: int | None = None, lang: str = "ru"
    ) -> list[dict]:
        context = []
        if subject:
            context.append(f"Предмет: {SUBJECTS.get(subject, subject)}.")
        if grade:
            context.append(f"Класс: {grade}. Подстрой сложность под этот класс.")
        prompt = (
            f"Ученик хочет разобраться в теме «{title}». {' '.join(context)}\n"
            "Сделай Stories-урок, как в Instagram: 6–10 карточек подряд, от простого к сложному. "
            "На карточке — одна мысль: title (2–5 слов), text — не больше 20 слов, emoji — один подходящий эмодзи. "
            "На 2–4 карточках (не на первой) добавь мини-вопрос по уже пройденному: question, "
            "options — 3 коротких варианта, correct — индекс верного (с 0), explanation — "
            "одно предложение, почему верно именно так.\n"
            f"{language_rule(lang)}\n"
            'Схема ответа: {"slides": [{"emoji": "…", "title": "…", "text": "…", '
            '"question": "…", "options": ["…", "…", "…"], "correct": 0, "explanation": "…"}]} — '
            "у карточек без вопроса поля question, options, correct и explanation не пиши."
        )
        return await self._ask(prompt, None, None, validate_stories, "stories")

    async def tutor_turn(
        self,
        problem: str,
        history: list[dict],
        photo: bytes | None = None,
        photo_mime: str | None = None,
        subject: str | None = None,
        grade: int | None = None,
        lang: str = "ru",
    ) -> dict:
        """Следующая реплика репетитора. Первый ход (history из одной реплики ученика) —
        ещё и problem: условие задачи своими словами (фото дальше не храним)."""
        first = len(history) <= 1
        context = []
        if subject:
            context.append(f"Предмет: {SUBJECTS.get(subject, subject)}.")
        if grade:
            context.append(f"Класс: {grade}.")
        schema = '{"problem": "…", "reply": "…", "solved": false}' if first else '{"reply": "…", "solved": false}'
        prompt = (
            f"{' '.join(context)}\n"
            + (f"Задача: {problem}\n" if problem else "")
            + ("К сообщению приложено фото задачи.\n" if photo else "")
            + f"Диалог:\n{tutor_transcript(history)}\n\n"
            + ("problem — условие задачи полностью, своими словами (без решения).\n" if first else "")
            + "Напиши следующую реплику репетитора. Формулы — обычным текстом (2x = 8, 3/8), без LaTeX и знаков $.\n"
            + f"{language_rule(lang)}\nСхема ответа: {schema}"
        )
        return await self._ask(
            prompt, photo, photo_mime, lambda d: validate_tutor_turn(d, first), "тьютор",
            system=TUTOR_PROMPT, temperature=0.4,
        )

    async def tutor_check(self, problem: str, history: list[dict], turn: dict) -> dict:
        prompt = (
            f"Задача: {problem}\nДиалог:\n{tutor_transcript(history)}\n\n"
            f"Проверяемая реплика репетитора: {json.dumps(turn, ensure_ascii=False)}"
        )
        return await self._ask(
            prompt, None, None, validate_tutor_check, "проверка тьютора",
            system=TUTOR_CHECK_PROMPT, temperature=0.0,
        )

    async def ielts_writing_prompt(self, task: int) -> dict:
        if task == 1:
            what = (
                "Write an IELTS Academic Writing Task 1: a chart description task. Choose ONE of bar, line, pie or "
                "table with realistic data (2–12 categories, 1–4 series; pie — exactly one series of percentages). "
                'prompt — the task text exactly as in the exam ("The chart below shows… Summarise the information by '
                'selecting and reporting the main features, and make comparisons where relevant. Write at least 150 words.").'
            )
            schema = (
                '{"prompt": "…", "chart": {"type": "bar", "title": "…", "unit": "%", '
                '"labels": ["2000", "2010"], "series": [{"name": "…", "values": [12, 18]}]}}'
            )
        else:
            what = (
                "Write an IELTS Writing Task 2 essay question on a topic teenagers can discuss (education, technology, "
                "environment, society…). Use a real exam format (opinion / discussion / problem–solution / "
                'advantages–disadvantages) and end with "Write at least 250 words."'
            )
            schema = '{"prompt": "…"}'
        for _ in range(2):
            material = await self._ask(
                f"{what}\nSchema: {schema}", None, None, lambda d: validate_writing_prompt(d, task), "IELTS задание",
                system=IELTS_WRITING_TASK_PROMPT, temperature=0.9,
            )
            if task == 2:
                return material
            # Проверка вторым запросом: текст задания должен точно соответствовать данным графика
            verdict = await self._ask(
                "Check this IELTS Writing Task 1. Does the task text match the chart data EXACTLY "
                "(number of categories/regions, years or periods, units, chart type)? "
                f"Task: {json.dumps(material, ensure_ascii=False)}\n"
                'Return {"ok": true, "issue": ""}.',
                None, None, validate_tutor_check, "проверка IELTS задания", system=IELTS_WRITING_TASK_PROMPT, temperature=0.0,
            )
            if verdict["ok"]:
                return material
            log.warning("IELTS Task 1 не совпадает с графиком: %s", verdict["issue"])
        raise GeminiError("IELTS Task 1: текст задания не совпадает с данными графика")

    async def ielts_test_material(self, kind: str) -> dict:
        """Reading / Listening: генерация и проверка вторым запросом — проверяющий сам отвечает
        на вопросы по тексту, в тест идут только вопросы, где его ответ совпал с ключом."""
        if kind == "reading":
            what = (
                "Write an IELTS Academic Reading passage (650–900 words, 5–6 paragraphs labelled A–F, an interesting "
                "science/history/society topic) and 13 questions: 5 mcq (4 options), 4 tfng (TRUE / FALSE / NOT GIVEN), "
                "4 gap (sentence completion with ____ , answer — NO MORE THAN THREE WORDS copied from the passage)."
            )
            schema = (
                '{"title": "…", "passage": "A …\\n\\nB …", "questions": ['
                '{"type": "mcq", "text": "…", "options": ["…", "…", "…", "…"], "answer": 0, "evidence": "…"}, '
                '{"type": "tfng", "text": "statement", "answer": "NOT GIVEN", "evidence": "…"}, '
                '{"type": "gap", "text": "The museum opened in ____.", "answer": "1851", "alternatives": [], "evidence": "…"}]}'
            )
        else:
            what = (
                "Write an IELTS Listening Part 1 or Part 2 recording: a natural everyday conversation between two speakers "
                "(booking, enquiry, tour, club registration…) of 400–600 words, as a script of short turns. "
                "Then 12 questions in the order the answers are heard: 6 gap (form/note completion with ____, answer — "
                "NO MORE THAN THREE WORDS AND/OR A NUMBER exactly as spoken; spell names out in the script) and 6 mcq (3 options). "
                "context — one line the examiner reads first."
            )
            schema = (
                '{"title": "…", "context": "You will hear…", "script": [{"speaker": "Receptionist", "text": "…"}, '
                '{"speaker": "Caller", "text": "…"}], "questions": ['
                '{"type": "gap", "text": "Name: Sarah ____", "answer": "Thompson", "alternatives": [], "evidence": "…"}, '
                '{"type": "mcq", "text": "…", "options": ["…", "…", "…"], "answer": 1, "evidence": "…"}]}'
            )
        last: Exception | None = None
        for _ in range(2):
            material = await self._ask(
                f"{what}\nSchema: {schema}", None, None, lambda d: validate_ielts_test(d, kind), f"IELTS {kind}",
                system=IELTS_TEST_PROMPT, temperature=0.8,
            )
            text = material["passage"] if kind == "reading" else "\n".join(f"{l['speaker']}: {l['text']}" for l in material["script"])
            blind = [{k: v for k, v in q.items() if k in ("type", "text", "options")} for q in material["questions"]]
            try:
                solved = await self._ask(
                    f"Text:\n{text}\n\nAnswer every question using ONLY the text. mcq — option index (from 0); "
                    "tfng — TRUE, FALSE or NOT GIVEN; gap — the missing words exactly as in the text.\n"
                    f"Questions: {json.dumps(blind, ensure_ascii=False)}\n"
                    'Return {"answers": [ … one per question, same order … ]}',
                    None, None, lambda d: d if isinstance(d, dict) and isinstance(d.get("answers"), list) else None,
                    f"проверка IELTS {kind}", system="You are a careful IELTS candidate. Return strict JSON.", temperature=0.0,
                )
            except GeminiError as exc:
                last = exc
                continue
            answers = solved["answers"]
            kept = [q for i, q in enumerate(material["questions"]) if i < len(answers) and ielts_answer_ok(q, answers[i])]
            if len(kept) >= IELTS_MIN_QUESTIONS:
                return {**material, "questions": kept}
            last = GeminiError(f"проверку прошли только {len(kept)} вопросов")
            log.warning("IELTS %s: %s", kind, last)
        raise GeminiError(f"IELTS {kind}: тест не прошёл проверку: {last}")

    async def ielts_speaking_material(self) -> dict:
        return await self._ask(
            "Write one full IELTS Speaking test on a single theme teenagers can talk about. part1 — 4 short personal "
            "questions; part2 — a cue card: topic (\"Describe …\") and 3–4 bullet points (\"You should say: …\"); "
            "part3 — 4 deeper discussion questions linked to the part 2 topic.\n"
            'Schema: {"theme": "…", "part1": ["…"], "part2": {"topic": "Describe …", "points": ["what …", "when …", '
            '"and explain …"]}, "part3": ["…"]}',
            None, None, validate_speaking_material, "IELTS Speaking задание",
            system=IELTS_WRITING_TASK_PROMPT, temperature=0.9,
        )

    async def ielts_speaking_turn(self, part: int, question: str, audio: bytes, mime: str) -> dict:
        schema = (
            '{"transcript": "…", "grammar": [{"quote": "exact words from transcript", "fix": "…", "explanation": "…"}], '
            '"vocabulary": [{"quote": "…", "better": "…"}], "pronunciation": [{"word": "…", "tip": "…"}], '
            '"comment": "one encouraging sentence + one thing to improve"}'
        )
        prompt = (
            f"IELTS Speaking Part {part}. Examiner's question: «{question}». The attached audio is the student's answer.\n"
            "If the audio is silent or not in English, return an empty transcript.\n"
            f"Schema: {schema}"
        )
        return await self._ask(
            prompt, audio, mime, validate_speaking_turn, "IELTS Speaking ответ",
            system=IELTS_SPEAKING_EXAMINER, temperature=0.2,
        )

    async def ielts_grade_speaking(self, turns: list[dict], examiner: str) -> dict:
        lines = []
        for t in turns:
            notes = "; ".join(f"{p['word']}: {p['tip']}" for p in t.get("pronunciation", []))
            lines.append(f"[Part {t['part']}] Q: {t['question']}\nA: {t['transcript']}" + (f"\n(pronunciation notes: {notes})" if notes else ""))
        schema = (
            '{"criteria": {"FC": {"band": 6.0, "comment": "…"}, "LR": {"band": 6.0, "comment": "…"}, '
            '"GRA": {"band": 6.0, "comment": "…"}, "P": {"band": 6.0, "comment": "…"}}, '
            '"summary": "2–3 sentences: strengths and the first thing to practise"}'
        )
        prompt = (
            "Full IELTS Speaking test transcript (answers transcribed from the student's audio, pronunciation notes "
            "from the audio in brackets):\n\n" + "\n\n".join(lines) + "\n\nGrade Fluency and Coherence, Lexical Resource, "
            "Grammatical Range and Accuracy and Pronunciation by the official band descriptors (0–9, step 0.5). "
            f"Be calibrated, do not inflate.\nSchema: {schema}"
        )
        return await self._ask(
            prompt, None, None, validate_speaking_grade, f"IELTS Speaking оценка ({examiner})",
            system=IELTS_EXAMINER_PROMPT.replace("Writing", "Speaking"), temperature=0.2 if examiner == "A" else 0.5,
        )

    async def ielts_grade_writing(self, task: int, prompt: str, essay: str, words: int, examiner: str) -> dict:
        minimum = 150 if task == 1 else 250
        schema = (
            '{"criteria": {"TR": {"band": 6.0, "comment": "…"}, "CC": {"band": 6.0, "comment": "…"}, '
            '"LR": {"band": 6.0, "comment": "…"}, "GRA": {"band": 6.0, "comment": "…"}}, '
            '"errors": [{"quote": "exact words from the essay", "type": "grammar", "fix": "…", "explanation": "…"}], '
            '"summary": "2–3 sentences: main strengths and what to improve first", '
            '"improved": "one improved paragraph of the student\'s essay"}'
        )
        prompt_text = (
            f"IELTS Writing Task {task}. Task:\n{prompt}\n\n"
            f"Student's answer ({words} words; minimum {minimum}):\n\"\"\"\n{essay}\n\"\"\"\n\n"
            "Grade it. List up to 15 most important errors (type: grammar, vocabulary, spelling, punctuation or style).\n"
            f"Schema: {schema}"
        )
        # Два экзаменатора: разная «температура» — независимые мнения, итог усредняет код
        temperature = 0.2 if examiner == "A" else 0.5
        return await self._ask(
            prompt_text, None, None, validate_writing_grade, f"IELTS оценка ({examiner})",
            system=IELTS_EXAMINER_PROMPT, temperature=temperature,
        )

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
