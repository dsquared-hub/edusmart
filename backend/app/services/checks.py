"""Проверка арифметики без ИИ.

Если в вопросе есть пример («Сколько будет 12 × 3?», «1/2 + 1/4 = ?»), считаем
его сами (точно, дробями) и сверяем с вариантом, который модель отметила
верным. Одиночная дробь «3/8» — это число, а не действие: такой вопрос
не проверяем, чтобы не было ложных срабатываний.
"""
from __future__ import annotations

import ast
import re
from fractions import Fraction

# Кусок текста, похожий на пример: цифры, скобки и знаки действий
_EXPR = re.compile(r"[\d(][\d\s.,()+\-−–×xх*·:÷/]*[\d)]")
_ACTION = re.compile(r"[+\-−–×xх*·:÷]")
_NUMBER = re.compile(r"^[−–-]?\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?$")

_PUNCT_COLON = re.compile(r"(?<=\d):(?=\s)")
_DOUBLE_OP = re.compile(r"[+\-*/]\s*[+*/]|^[*/]|[+\-*/]$")

MAX_VALUE = 10**12


def _normalize(expr: str) -> str:
    table = {"×": "*", "x": "*", "х": "*", "·": "*", ":": "/", "÷": "/", "−": "-", "–": "-", ",": "."}
    return "".join(table.get(ch, ch) for ch in expr)


def _eval(node) -> Fraction:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return Fraction(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _eval(node.operand)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Add):
            result = left + right
        elif isinstance(node.op, ast.Sub):
            result = left - right
        elif isinstance(node.op, ast.Mult):
            result = left * right
        else:
            if right == 0:
                raise ValueError("деление на ноль")
            result = left / right
        if abs(result) > MAX_VALUE:
            raise ValueError("слишком большое число")
        return result
    raise ValueError("не арифметика")


def safe_eval(expr: str) -> Fraction | None:
    """Считает только + − × ÷ и скобки. Никакого eval() — разбор через ast."""
    text = _normalize(expr).strip()
    if not text or len(text) > 80:
        return None
    # «2x + 3» → «2* + 3»: два знака подряд — это алгебра, а не пример
    if _DOUBLE_OP.search(text):
        return None
    try:
        return _eval(ast.parse(text, mode="eval"))
    except (SyntaxError, ValueError, ZeroDivisionError, RecursionError):
        return None


def parse_number(text: str) -> Fraction | None:
    """«12», «0,5», «-3», «3/8» → число. Всё остальное (слова, единицы) → None."""
    value = text.strip().rstrip(".").replace(" ", "")
    if not _NUMBER.match(value):
        return None
    return safe_eval(value)


def question_value(question: str) -> Fraction | None:
    """Значение примера из вопроса, если там явно есть действие."""
    # «ближе к 1: 1/4 или 3/4» — двоеточие после числа и пробел: это знак
    # препинания, а не деление («12 : 4», «12:4»). Разрываем пример в этом месте.
    question = _PUNCT_COLON.sub(" ; ", question)
    best: str | None = None
    for match in _EXPR.finditer(question):
        candidate = match.group().strip()
        if _ACTION.search(candidate) and (best is None or len(candidate) > len(best)):
            best = candidate
    return safe_eval(best) if best else None


def arithmetic_fix(question: str, options: list[str], correct: int) -> int | None:
    """Индекс, который на самом деле верный, если модель ошиблась. Иначе None.

    Срабатывает, только когда ровно один вариант совпал с посчитанным ответом —
    если совпадений нет или их несколько, вопрос не про этот пример.
    """
    value = question_value(question)
    if value is None:
        return None
    matches = [i for i, option in enumerate(options) if parse_number(option) == value]
    if len(matches) == 1 and matches[0] != correct:
        return matches[0]
    return None
