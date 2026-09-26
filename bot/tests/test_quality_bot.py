"""Бот: жалобы на ошибки, очки за попытки, лимит упрощений, удаление данных, версия политики."""
from __future__ import annotations

from app.core.config import get_settings
from app.db.models import User
from app.db.session import SessionLocal
from app.repositories.students import get_student
from bot.events_worker import process_events_once
from conftest import OWNER
from test_bot_flow import CORRECT, KID, MOM, TEACHER, _student_with_consent, _topic


async def _start_topic(h) -> int:
    kid_id = await _student_with_consent(h)
    await h.press(KID, "student:help")
    await h.send(KID, "дроби")
    return kid_id


async def test_step_has_report_button_and_report_reaches_owner_and_teacher(h):
    kid_id = await _start_topic(h)
    topic = await _topic(kid_id)
    await h.press(KID, f"quiz:{topic.id}")
    assert f"rep:{topic.id}:0" in h.callback_data(h.api.last(KID))

    # учитель ученика
    async with SessionLocal() as s:
        code = (await get_student(s, kid_id)).family_code
    await h.send(TEACHER, "/start", name="Учитель")
    await h.register(TEACHER, "teacher", name="Учитель")
    await h.press(TEACHER, "teacher:bind", name="Учитель")
    await h.send(TEACHER, code, name="Учитель")

    await h.press(KID, f"rep:{topic.id}:0")
    assert "Спасибо" in h.api.alerts()[-1]
    await h.press(KID, f"rep:{topic.id}:0")
    assert "уже сообщил" in h.api.alerts()[-1]

    await process_events_once(h.bot)
    for chat in (OWNER, TEACHER):
        text = h.api.last(chat).text
        assert "Жалоба на объяснение" in text and "3/8" in text

    await h.send(TEACHER, "/reports", name="Учитель")
    listing = h.api.last(TEACHER)
    assert "Открытые жалобы" in listing.text
    report_button = [d for d in h.callback_data(listing) if d.startswith("resolve:")][0]
    await h.press(KID, report_button)  # ученик не может закрыть жалобу
    assert "недоступно" in h.api.alerts()[-1]
    await h.press(TEACHER, report_button, name="Учитель")
    assert "разобранная" in h.api.alerts()[-1]
    await h.send(OWNER, "/reports", name="Владелец")
    assert "Открытых жалоб нет" in h.api.last(OWNER).text


async def test_reports_only_for_teacher_or_owner(h):
    await h.send(KID, "/reports")
    assert "недоступно" in h.api.last(KID).text


async def test_wrong_answer_gives_no_points_and_moves_on(h):
    """В боте после ошибки — разбор и следующий вопрос; перебором очки не набрать."""
    kid_id = await _start_topic(h)
    topic = await _topic(kid_id)
    await h.press(KID, f"ans:{topic.id}:0:1")  # ошибка
    await h.press(KID, f"ans:{topic.id}:0:0")  # старая кнопка того же вопроса
    assert "уже продвинулся" in h.api.texts(KID)[-2]
    assert "Вопрос 2 из 4" in h.api.last(KID).text
    await h.press(KID, f"ans:{topic.id}:1:1")
    assert "+10 очков" in h.api.last(KID).text
    async with SessionLocal() as s:
        assert (await get_student(s, kid_id)).points == 10
    topic = await _topic(kid_id)
    assert topic.current_step == 2 and topic.wrong_count == 0


async def test_consent_shows_policy_version(h):
    await _student_with_consent(h)
    await h.press(MOM, "parent:consent", name="Мама")
    text = h.api.last(MOM).text
    assert f"Версия политики: {get_settings().policy_version}" in text
    urls = [b.url for b in h.buttons(h.api.last(MOM)) if b.url]
    assert urls == ["https://edu.example.com/privacy"]


async def test_parent_deletes_child_data(h):
    kid_id = await _student_with_consent(h)
    await h.press(MOM, "parent:profile", name="Мама")
    assert f"delchild:{kid_id}" in h.callback_data(h.api.last(MOM))

    await h.press(KID, f"delchild:{kid_id}")  # чужой — не видит даже имени
    assert "недоступно" in h.api.alerts()[-1]

    await h.press(MOM, f"delchild:{kid_id}", name="Мама")
    assert "нельзя отменить" in h.api.last(MOM).text
    await h.press(MOM, "delchild:no", name="Мама")
    assert "отменено" in h.api.last(MOM).text

    await h.press(MOM, f"delchild:yes:{kid_id}", name="Мама")
    assert "удалены" in h.api.last(MOM).text
    async with SessionLocal() as s:
        assert await s.get(User, kid_id) is None
    # Ребёнок может начать заново как новый пользователь
    await h.send(KID, "/start")
    assert "Кто вы?" in h.api.last(KID).text


async def test_full_flow_points_total(h):
    kid_id = await _start_topic(h)
    topic = await _topic(kid_id)
    for step, option in enumerate(CORRECT):
        await h.press(KID, f"ans:{topic.id}:{step}:{option}")
    async with SessionLocal() as s:
        assert (await get_student(s, kid_id)).points == 40  # всё с первой попытки
