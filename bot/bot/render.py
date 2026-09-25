"""Тексты шагов для Telegram (HTML). Схемы visual показываем текстом."""
from __future__ import annotations

from html import escape

from app.core.i18n import t
from app.db.models import ContentReport, Topic


def _num(value) -> str:
    return f"{value:g}" if isinstance(value, (int, float)) else str(value)


def _fraction(item: dict) -> str:
    num, den = int(item["numerator"]), int(item["denominator"])
    label = item.get("label") or f"{num}/{den}"
    if not (0 < den <= 12) or not (0 <= num <= den):
        return label
    return "●" * num + "○" * (den - num) + " " + label


def visual_text(visual: dict | None) -> str:
    """Короткое текстовое представление схемы (на сайте она рисуется как SVG)."""
    if not visual:
        return ""
    data = visual.get("data") or {}
    vtype = visual.get("type")
    line = ""
    try:
        if vtype == "arrows":
            line = " → ".join(str(x) for x in data.get("items", []))
        elif vtype == "fractions":
            line = "  ".join(_fraction(i) for i in data.get("items", []))
        elif vtype == "number_line":
            marks = data.get("marks") or []
            line = " ── ".join(str(m.get("label") or _num(m.get("value"))) for m in marks)
        elif vtype == "table":
            rows = [data.get("headers") or []] + list(data.get("rows") or [])
            line = "\n".join(" | ".join(str(c) for c in row) for row in rows if row)
        elif vtype == "cards":
            line = "\n".join(
                f"▫️ {c.get('title', '')}: {c.get('text', '')}" for c in data.get("items", [])
            )
    except (TypeError, ValueError, KeyError, AttributeError):
        line = ""
    caption = visual.get("caption") or ""
    parts = [escape(p) for p in (line, caption) if p]
    return "🖼 " + "\n".join(parts) if parts else ""


MESSAGE_LIMIT = 4000  # у Telegram 4096, оставляем запас на разметку


def explanation_block(step: dict, index: int) -> str:
    """Одна часть объяснения темы — без вопроса."""
    parts = [
        f"<b>{index + 1}. {escape(step['title'])}</b>",
        escape(step["text"]),
        f"{t('example_label')} {escape(step['example'])}",
    ]
    vis = visual_text(step.get("visual"))
    if vis:
        parts.append(vis)
    return "\n\n".join(parts)


def lesson_messages(topic: Topic) -> list[str]:
    """Объяснение всей темы: всё в одном сообщении, если влезает, иначе — по частям."""
    header = t("lesson_header", title=escape(topic.title or ""))
    blocks = [explanation_block(step, i) for i, step in enumerate(topic.steps)]
    messages: list[str] = []
    current = header
    for block in blocks:
        candidate = f"{current}\n\n{block}"
        if len(candidate) > MESSAGE_LIMIT and current != header:
            messages.append(current)
            current = block
        else:
            current = candidate
    messages.append(current)
    return messages


def question_text(step: dict, index: int, total: int) -> str:
    return f"{t('question_header', n=index + 1, total=total)}\n\n❓ {escape(step['check_question'])}"


def review_text(step: dict, index: int, total: int, option: int, verdict: str) -> str:
    """Разбор выбранного варианта: почему он верный/неверный, и верный ответ при ошибке."""
    options = step["options"]
    correct = step["correct"]
    explanations = step.get("explanations") or []
    parts = [question_text(step, index, total), verdict]
    chosen = t("review_chosen", option=escape(options[option]))
    if len(explanations) == len(options):
        chosen += f"\n{escape(explanations[option])}"
    parts.append(chosen)
    if option != correct:
        right = t("review_correct", option=escape(options[correct]))
        if len(explanations) == len(options):
            right += f"\n{escape(explanations[correct])}"
        else:
            # Старая тема без пояснений — напоминаем, о чём был этот шаг
            right += f"\n{escape(step['text'])}"
        parts.append(right)
    return "\n\n".join(parts)


def describe(report: ContentReport, topic: Topic) -> dict:
    """Что именно оспаривают: вопрос и ответ, отмеченный верным."""
    if report.kind == "practice":
        items = topic.practice or []
        item = items[report.step_index] if report.step_index < len(items) else {}
        question = item.get("question", "")
    else:
        items = topic.steps or []
        item = items[report.step_index] if report.step_index < len(items) else {}
        question = item.get("check_question", "")
    options, correct = item.get("options") or [], item.get("correct", 0)
    answer = options[correct] if 0 <= correct < len(options) else "—"
    return {
        "kind": t(f"report_kind_{report.kind}"),
        "n": report.step_index + 1,
        "question": escape(question),
        "answer": escape(str(answer)),
        "title": escape(topic.title or ""),
    }
