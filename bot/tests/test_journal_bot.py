"""Бот: журнал результатов (/journal) для родителя и учителя."""
from __future__ import annotations

import re

from app.db.session import SessionLocal
from app.repositories.students import get_student
from test_bot_flow import CORRECT, KID, MOM, TEACHER, _student_with_consent, _topic


async def _finish_topic(h, kid_id: int, title: str, wrong_first: bool = False) -> None:
    await h.press(KID, "student:help")
    await h.send(KID, title)
    topic = await _topic(kid_id)
    for step in range(4):
        await h.press(KID, f"quiz:{topic.id}")
        option = (CORRECT[step] + 1) % 3 if wrong_first and step == 0 else CORRECT[step]
        await h.press(KID, f"ans:{topic.id}:{step}:{option}")
    assert "Тема закрыта" in h.api.last(KID).text


async def _bind_teacher(h, kid_id: int) -> None:
    async with SessionLocal() as s:
        code = (await get_student(s, kid_id)).family_code
    await h.send(TEACHER, "/start", name="Учитель")
    await h.register(TEACHER, "teacher", name="Учитель")
    await h.press(TEACHER, "teacher:bind", name="Учитель")
    await h.send(TEACHER, code, name="Учитель")


async def test_parent_journal_shows_results(h):
    kid_id = await _student_with_consent(h)
    await h.send(MOM, "/start", name="Мама")
    assert "journal:all" in h.callback_data(h.api.last(MOM))

    await h.send(MOM, "/journal", name="Мама")
    empty = h.api.last(MOM).text
    assert "Журнал результатов" in empty and "Закрытых тем пока нет" in empty

    await _finish_topic(h, kid_id, "дроби", wrong_first=True)
    await h.press(MOM, "journal:all", name="Мама")
    text = h.api.last(MOM).text
    assert "Закрыто тем: 1 (за неделю: 1)" in text
    assert "Верно с первой попытки: 75%" in text
    assert "«дроби» — ✔️ 3 из 4 с первой попытки · ❌ ошибок: 1 · ⭐ +30" in text
    # единственный ребёнок — имя в строках результатов не повторяем
    assert re.search(r"🗓 \d\d\.\d\d \d\d:\d\d\n«дроби»", text)
    urls = [b.web_app.url for b in h.buttons(h.api.last(MOM)) if b.web_app]
    assert urls == ["https://edu.example.com/journal"]


async def test_teacher_journal_and_menu_button(h):
    kid_id = await _student_with_consent(h)
    await _bind_teacher(h, kid_id)
    await h.send(TEACHER, "/start", name="Учитель")
    assert "journal:all" in h.callback_data(h.api.last(TEACHER))

    await _finish_topic(h, kid_id, "проценты")
    await h.press(TEACHER, "journal:all", name="Учитель")
    text = h.api.last(TEACHER).text
    assert "«проценты» — ✔️ 4 из 4" in text and "100%" in text

    # фильтр по ученику: свой — открывается, с кнопкой «Весь журнал»
    await h.press(TEACHER, f"journal:{kid_id}", name="Учитель")
    assert "«проценты»" in h.api.last(TEACHER).text
    assert "journal:all" in h.callback_data(h.api.last(TEACHER))


async def test_journal_not_for_students_or_foreign(h):
    kid_id = await _student_with_consent(h)
    await h.send(KID, "/journal")
    assert "родителям и учителям" in h.api.last(KID).text

    await h.send(TEACHER, "/start", name="Учитель")
    await h.register(TEACHER, "teacher", name="Учитель")
    await h.send(TEACHER, "/journal", name="Учитель")
    assert "пока нет учеников" in h.api.last(TEACHER).text
    await h.press(TEACHER, f"journal:{kid_id}", name="Учитель")  # чужой ученик
    assert "недоступно" in h.api.last(TEACHER).text
