"""Демо-заглушка вместо Gemini: для тестов и запуска без API-ключа.

Всегда отвечает одним и тем же объяснением про дроби — в нём есть все типы схем.
"""
from __future__ import annotations

import copy

from app.services.gemini import GeminiError

_STEPS = [
    {
        "title": "Дробь — это часть целого",
        "text": "Представь пиццу. Её разрезали на 4 равных куска. Один кусок — это одна четвёртая.",
        "example": "Ты съел 1 кусок из 4 — значит, ты съел 1/4 пиццы.",
        "visual": {
            "type": "fractions",
            "data": {"items": [{"numerator": 1, "denominator": 4, "label": "1/4"}]},
            "caption": "Закрашен 1 кусок из 4",
        },
        "check_question": "Пиццу разрезали на 8 кусков, ты взял 3. Какая это дробь?",
        "options": ["3/8", "8/3", "3/5"],
        "correct": 0,
        "explanations": [
            "Пиццу делили на 8 частей — это низ дроби, взяли 3 — это верх.",
            "Числа перепутаны: внизу пишут, на сколько частей делили, а это 8.",
            "5 — это сколько кусков осталось, а делили пиццу на 8.",
        ],
    },
    {
        "title": "Верх и низ дроби",
        "text": "Нижнее число — на сколько частей разделили. Верхнее — сколько частей взяли.",
        "example": "В 2/5 целое разделили на 5 частей и взяли 2.",
        "visual": {
            "type": "cards",
            "data": {
                "items": [
                    {"title": "Числитель", "text": "сверху: сколько взяли"},
                    {"title": "Знаменатель", "text": "снизу: на сколько делили"},
                ]
            },
            "caption": "Два числа — две роли",
        },
        "check_question": "Что показывает знаменатель?",
        "options": ["Сколько частей взяли", "На сколько частей делили", "Сколько всего пицц"],
        "correct": 1,
        "explanations": [
            "Сколько взяли — это числитель, он сверху.",
            "Знаменатель снизу и показывает, на сколько равных частей разделили целое.",
            "Дробь говорит о частях одного целого, а не о количестве пицц.",
        ],
    },
    {
        "title": "Дроби на числовой прямой",
        "text": "Дробь — тоже число. Её можно поставить на прямую между 0 и 1.",
        "example": "1/2 стоит ровно посередине между 0 и 1.",
        "visual": {
            "type": "number_line",
            "data": {
                "min": 0,
                "max": 1,
                "marks": [
                    {"value": 0, "label": "0"},
                    {"value": 0.5, "label": "1/2"},
                    {"value": 1, "label": "1"},
                ],
                "highlight": [0, 0.5],
            },
            "caption": "Половина пути от 0 до 1",
        },
        "check_question": "Где на прямой стоит 1/2?",
        "options": ["Правее 1", "Посередине между 0 и 1", "Левее 0"],
        "correct": 1,
        "explanations": [
            "Правее 1 стоят числа больше целого, а половина меньше целого.",
            "Половина — это ровно полпути от 0 до 1.",
            "Левее 0 — отрицательные числа, а 1/2 больше нуля.",
        ],
    },
    {
        "title": "Сравниваем дроби",
        "text": "Если знаменатели одинаковые, больше та дробь, у которой больше числитель.",
        "example": "3/5 больше, чем 2/5: три куска больше двух.",
        "visual": {
            "type": "arrows",
            "data": {"items": ["Знаменатели равны?", "Сравни числители", "Больше числитель — больше дробь"]},
            "caption": "Как сравнить за 3 шага",
        },
        "check_question": "Что больше: 4/7 или 2/7?",
        "options": ["2/7", "Они равны", "4/7"],
        "correct": 2,
        "explanations": [
            "Знаменатели одинаковые, а у 2/7 числитель меньше — значит, и дробь меньше.",
            "Равны были бы, если бы совпадали и числители, а здесь 4 и 2.",
            "Знаменатели одинаковые, а 4 куска больше 2 — значит, 4/7 больше.",
        ],
    },
]

_PRACTICE = [
    {"question": "Торт разрезали на 6 частей, съели 1. Какая часть съедена?",
     "options": ["1/6", "6/1", "5/6"], "correct": 0,
     "hint": "Внизу — на сколько частей разрезали."},
    {"question": "Что больше: 5/9 или 7/9?", "options": ["5/9", "7/9", "Равны"],
     "correct": 1, "hint": "Знаменатели одинаковые — смотри на числители."},
    {"question": "Какая дробь стоит ближе к 1: 1/4 или 3/4?",
     "options": ["1/4", "3/4"], "correct": 1,
     "hint": "3 куска из 4 — это почти целое."},
]


_STORIES = [
    {"emoji": "🍕", "title": "Что такое дробь", "text": "Дробь — это часть целого. Пиццу разрезали на части — каждая часть и есть дробь."},
    {"emoji": "⬇️", "title": "Знаменатель", "text": "Число внизу — на сколько равных частей разделили целое."},
    {"emoji": "⬆️", "title": "Числитель", "text": "Число вверху — сколько таких частей взяли."},
    {"emoji": "🤔", "title": "Проверим", "text": "Пиццу разрезали на 8 частей, ты съел 3.",
     "question": "Какую часть пиццы ты съел?", "options": ["3/8", "8/3", "5/8"], "correct": 0,
     "explanation": "Вверху — сколько взяли (3), внизу — на сколько частей делили (8)."},
    {"emoji": "⚖️", "title": "Сравниваем", "text": "Если знаменатели равны, больше та дробь, у которой больше числитель."},
    {"emoji": "🏁", "title": "Запомни", "text": "Внизу — сколько частей всего, вверху — сколько взяли.",
     "question": "Что больше: 5/9 или 7/9?", "options": ["5/9", "7/9", "Равны"], "correct": 1,
     "explanation": "Знаменатели одинаковые, а 7 больше 5."},
]


class StubLessonService:
    # Рычаги для тестов
    fail_next: bool = False  # сымитировать ошибку модели
    wrong_answers: int = 0  # столько следующих объяснений придут с неверным «correct»
    verifier_disagrees: bool = False  # проверяющий всегда «не согласен»
    verify_calls: int = 0

    async def explain_topic(self, title, photo=None, photo_mime=None, subject=None, grade=None, lang="ru"):
        if self.fail_next:
            self.fail_next = False
            raise GeminiError("Имитация ошибки")
        steps = copy.deepcopy(_STEPS)
        if self.wrong_answers > 0:
            self.wrong_answers -= 1
            steps[0]["correct"] = 1  # «8/3» вместо «3/8» — ошибка модели
        return steps

    async def make_stories(self, title, subject=None, grade=None, lang="ru"):
        if self.fail_next:
            self.fail_next = False
            raise GeminiError("Имитация ошибки")
        slides = copy.deepcopy(_STORIES)
        if self.wrong_answers > 0:
            self.wrong_answers -= 1
            slides[3]["correct"] = 1  # «8/3» вместо «3/8» — ошибка модели
        return slides

    tutor_leaks: int = 0  # столько следующих реплик тьютора «выдадут ответ» — проверка должна их отбраковать

    async def tutor_turn(self, problem, history, photo=None, photo_mime=None, subject=None, grade=None, lang="ru"):
        """Демо-репетитор: задача 3/8 + 2/8, ответ 5/8 ученик должен назвать сам."""
        if self.fail_next:
            self.fail_next = False
            raise GeminiError("Имитация ошибки")
        first = len(history) <= 1
        last = history[-1]["text"] if history else ""
        if self.tutor_leaks > 0:
            self.tutor_leaks -= 1
            turn = {"reply": "Ответ: 5/8.", "solved": False}
        elif not first and "5/8" in last.replace(" ", ""):
            turn = {"reply": "Верно! Знаменатель тот же, числители сложили: получилось 5/8 🎉", "solved": True}
        elif not first and "8" in last:
            turn = {"reply": "Да, знаменатель остаётся 8. А что делаем с числителями 3 и 2?", "solved": False}
        else:
            turn = {"reply": "Посмотри на знаменатели дробей. Что с ними происходит при сложении?", "solved": False}
        if first:
            turn["problem"] = "Сложи дроби: 3/8 + 2/8."
        return turn

    async def tutor_check(self, problem, history, turn):
        """Проверяющий: ответ «5/8» может назвать только ученик."""
        said = any("5/8" in m["text"].replace(" ", "") for m in history if m["role"] == "student")
        leaked = "5/8" in turn["reply"] and not said
        return {"ok": not leaked, "issue": "выдан ответ" if leaked else ""}

    async def ielts_writing_prompt(self, task):
        if task == 1:
            return {
                "task": 1,
                "prompt": "The chart below shows the percentage of households with internet access in three countries "
                          "in 2000 and 2020. Summarise the information by selecting and reporting the main features, "
                          "and make comparisons where relevant. Write at least 150 words.",
                "chart": {"type": "bar", "title": "Households with internet access", "unit": "%",
                          "labels": ["Uzbekistan", "Kazakhstan", "UK"],
                          "series": [{"name": "2000", "values": [2.0, 4.0, 45.0]}, {"name": "2020", "values": [76.0, 88.0, 96.0]}]},
            }
        return {"task": 2, "prompt": "Some people think that students should study at home online rather than at school. "
                                     "To what extent do you agree or disagree? Write at least 250 words."}

    async def ielts_speaking_material(self):
        return {
            "theme": "Hobbies",
            "part1": ["Do you have a hobby?", "How much free time do you have?", "Do you like sports?", "What did you do last weekend?"],
            "part2": {"topic": "Describe a hobby you enjoy", "points": ["what it is", "when you started", "who you do it with", "and explain why you enjoy it"]},
            "part3": ["Why do people need hobbies?", "Are hobbies expensive?", "How have hobbies changed?", "Should schools teach hobbies?"],
        }

    async def ielts_speaking_turn(self, part, question, audio, mime):
        """Тишина (пустое аудио) — пустая расшифровка; иначе — фиксированный ответ с ошибками."""
        if audio.strip(b"\x00") == b"":
            return {"transcript": "", "grammar": [], "vocabulary": [], "pronunciation": [], "comment": ""}
        return {
            "transcript": "I likes playing football with my friends every weekend.",
            "grammar": [
                {"quote": "I likes", "fix": "I like", "explanation": "No -s after I."},
                {"quote": "he go", "fix": "he goes", "explanation": "Not in the answer — must be dropped."},
            ],
            "vocabulary": [{"quote": "playing football", "better": "playing five-a-side football"}],
            "pronunciation": [{"word": "weekend", "tip": "Stress the first syllable."}, {"word": "zebra", "tip": "Not said."}],
            "comment": "Good fluency; check verb endings.",
        }

    async def ielts_grade_speaking(self, turns, examiner):
        base = 6.0
        return {
            "criteria": {
                "FC": {"band": base, "comment": "Speaks at length."},
                "LR": {"band": base + (0.5 if examiner == "A" else 0.0), "comment": "Adequate range."},
                "GRA": {"band": base - 0.5, "comment": "Frequent errors in verb forms."},
                "P": {"band": base, "comment": "Generally clear."},
            },
            "summary": "Keep practising verb endings.",
        }

    async def ielts_test_material(self, kind):
        """Демо-тест: ключ ответов известен (вопросы 0–5 — mcq, дальше — tfng/gap)."""
        questions = [
            {"type": "mcq", "text": f"Question {i + 1}: what is {i} + 1?", "options": [str(i + 1), str(i + 2), str(i + 3)],
             "answer": 0, "evidence": f"{i} plus one is {i + 1}."}
            for i in range(6)
        ]
        if kind == "reading":
            questions += [{"type": "tfng", "text": f"Statement {i}", "answer": ("TRUE", "FALSE", "NOT GIVEN")[i % 3], "evidence": ""} for i in range(3)]
            questions += [
                {"type": "gap", "text": "The bridge was built in ____.", "answer": "1889", "alternatives": [], "evidence": "…in 1889."},
                {"type": "gap", "text": "It is made of ____.", "answer": "iron", "alternatives": ["wrought iron"], "evidence": "…of wrought iron."},
            ]
            return {"kind": "reading", "title": "The Iron Bridge", "passage": "A The bridge was built in 1889 of wrought iron. " * 40,
                    "questions": questions}
        questions += [
            {"type": "gap", "text": f"Detail {i}: ____", "answer": f"word{i}", "alternatives": [], "evidence": ""} for i in range(5)
        ]
        script = [{"speaker": "Receptionist" if i % 2 == 0 else "Caller", "text": f"Line {i} of the booking call."} for i in range(8)]
        return {"kind": "listening", "title": "Booking a room", "context": "You will hear a phone call.", "script": script,
                "questions": questions}

    async def ielts_grade_writing(self, task, prompt, essay, words, examiner):
        """Детерминированный экзаменатор: коротко — ниже балл; второй экзаменатор строже к лексике.
        Одна ошибка цитирует эссе дословно, другая — выдуманная (код должен её отбросить)."""
        base = 6.5 if words >= (150 if task == 1 else 250) else 5.0
        lr = base - (0.5 if examiner == "B" else 0.0)
        quote = " ".join(essay.split()[:3]) or "—"
        return {
            "criteria": {
                "TR": {"band": base, "comment": "Clear position."},
                "CC": {"band": base, "comment": "Logical paragraphs."},
                "LR": {"band": lr, "comment": "Some repetition."},
                "GRA": {"band": base, "comment": "Mostly accurate."},
            },
            "errors": [
                {"quote": quote, "type": "grammar", "fix": quote.capitalize(), "explanation": "Start with a capital letter."},
                {"quote": "a phrase that is not in the essay", "type": "vocabulary", "fix": "—", "explanation": "—"},
            ],
            "summary": "Good structure; work on vocabulary range.",
            "improved": "In my opinion, studying at school is more effective than learning online.",
        }

    async def verify_answers(self, items):
        """Проверяющий знает правильные ответы демо-урока, задач и Stories."""
        self.verify_calls += 1
        truth = {s["check_question"]: s["correct"] for s in _STEPS}
        truth.update({p["question"]: p["correct"] for p in _PRACTICE})
        truth.update({s["question"]: s["correct"] for s in _STORIES if "question" in s})
        results = []
        for item in items:
            right = truth.get(item["question"], item["correct"])
            if self.verifier_disagrees:
                right = (item["correct"] + 1) % len(item["options"])
            ok = right == item["correct"]
            results.append({"ok": ok, "correct": right, "issue": "" if ok else "неверный ответ"})
        return results

    async def explain_step_simpler(self, title, step, step_index, total_steps, lang="ru"):
        return {
            "title": "Ещё проще",
            "text": f"Давай медленно. {step['text'].split('.')[0]}.",
            "example": "Как если бы ты делил яблоко с другом.",
            "visual": {
                "type": "fractions",
                "data": {"items": [{"numerator": 1, "denominator": 2, "label": "1/2"}]},
                "caption": "Половинка яблока",
            },
            "check_question": step["check_question"],
            "options": list(step["options"]),
            "correct": step["correct"],
        }

    async def make_practice(self, title, steps, lang="ru"):
        return copy.deepcopy(_PRACTICE)
