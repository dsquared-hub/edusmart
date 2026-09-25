"""Проверка арифметики без ИИ: ловит ошибки модели и не даёт ложных тревог."""
from __future__ import annotations

from fractions import Fraction

import pytest

from app.services.checks import arithmetic_fix, parse_number, question_value, safe_eval


@pytest.mark.parametrize(
    "question, value",
    [
        ("Сколько будет 12 × 3?", 36),
        ("Сколько будет 1/2 + 1/4?", Fraction(3, 4)),
        ("Реши: (7 − 2) · 4 = ?", 20),
        ("12 : 4 = ?", 3),
        ("Сколько будет 12:4?", 3),
        ("0,5 + 1,25 = ?", Fraction(7, 4)),
        ("Hisobla: 15 - 6", 9),
    ],
)
def test_question_value(question, value):
    assert question_value(question) == value


@pytest.mark.parametrize(
    "question",
    [
        "Пиццу разрезали на 8 кусков, ты взял 3. Какая это дробь?",  # нет примера
        "Где на прямой стоит 1/2?",  # дробь — число, а не действие
        "Что больше: 4/7 или 2/7?",
        "Реши уравнение 2x + 3 = 7",  # алгебра — не наш случай
        "Какая дробь стоит ближе к 1: 1/4 или 3/4?",  # двоеточие — знак препинания
        "Ответ на шаг 2: 3/8 пиццы",
    ],
)
def test_no_false_positives(question):
    assert arithmetic_fix(question, ["3/8", "8/3", "7", "2"], 0) is None


def test_algebra_is_not_arithmetic():
    assert question_value("Реши уравнение 2x + 3 = 7") is None
    assert question_value("Найди x, если x - 4 = 10") is None


def test_fixes_wrong_correct_index():
    assert arithmetic_fix("Сколько будет 12 × 3?", ["33", "36", "39"], 0) == 1
    assert arithmetic_fix("Сколько будет 12 × 3?", ["33", "36", "39"], 1) is None
    # ответ не среди вариантов — вопрос не про этот пример, не трогаем
    assert arithmetic_fix("Сколько будет 12 × 3?", ["много", "мало"], 0) is None


def test_safe_eval_rejects_code():
    assert safe_eval("__import__('os').system('echo hi')") is None
    assert safe_eval("1/0") is None
    assert safe_eval("9" * 20 + "*" + "9" * 20) is None
    assert parse_number("3/8") == Fraction(3, 8)
    assert parse_number("12 яблок") is None
