"""Бот для взрослых: регистрация родителя/учителя и ребёнка; ребёнку — ссылка на приложение."""
from __future__ import annotations

from datetime import datetime

import pytest
from aiogram.types import Chat, Contact, Message, Update
from sqlalchemy import select

from app.core.config import get_settings
from app.core.timeutil import local_now
from app.db.models import Event, FamilyMember, Student, User
from app.db.session import SessionLocal
from app.repositories.students import get_children
from app.repositories.users import get_by_telegram
from app.services.accounts import login_code
from bot.events_worker import process_events_once
from bot.scheduler import evening_reminders, parent_reminders
from conftest import _ids

MOM, TEACHER, KID = 7001, 7002, 7003


@pytest.fixture
def adults_only(monkeypatch):
    monkeypatch.setattr(get_settings(), "bot_student_lessons", False)


async def _contact(h, uid: int, phone: str, owner: int | None = None, name: str = "Мама") -> None:
    message = Message(
        message_id=next(_ids),
        date=datetime.now(),
        chat=Chat(id=uid, type="private"),
        from_user=h._tg_user(uid, name),
        contact=Contact(phone_number=phone, first_name=name, user_id=owner or uid),
    )
    await h._feed(Update(update_id=next(_ids), message=message))


def _reply_buttons(request) -> list:
    markup = getattr(request, "reply_markup", None)
    return [b for row in getattr(markup, "keyboard", None) or [] for b in row]


async def _register_parent(h, phone: str | None = "+998 90 123 45 67") -> None:
    await h.send(MOM, "/start", name="Мама")
    await h.press(MOM, "role:parent", name="Мама")
    assert "Как к вам обращаться" in h.api.last(MOM).text
    assert h.callback_data(h.api.last(MOM)) == ["reg:keepname"]
    await h.send(MOM, "Малика Юсупова", name="Мама")
    ask = h.api.last(MOM)
    assert "номером телефона" in ask.text
    assert _reply_buttons(ask)[0].request_contact
    if phone:
        await _contact(h, MOM, phone)
    else:
        await h.send(MOM, "Пропустить", name="Мама")


async def test_start_is_for_adults(h, adults_only):
    await h.send(KID, "/start", name="Тимур")
    msg = h.api.last(KID)
    assert "родителей и учителей" in msg.text and "https://edu.example.com/" in msg.text
    assert h.callback_data(msg) == ["role:parent", "role:teacher", "lang:menu"]
    await h.press(KID, "role:student", name="Тимур")  # старая кнопка
    assert "приложении EDU" in h.api.alerts()[-1]
    async with SessionLocal() as s:
        assert (await get_by_telegram(s, KID)).role is None


async def test_parent_registers_self_and_child(h, adults_only):
    await _register_parent(h)
    texts = h.api.texts(MOM)
    assert "Готово, Малика Юсупова" in texts[-2]
    assert h.callback_data(h.api.last(MOM)) == ["reg:child", "parent:bind", "reg:menu"]
    async with SessionLocal() as s:
        mom = await get_by_telegram(s, MOM)
        assert (mom.role, mom.full_name, mom.phone) == ("parent", "Малика Юсупова", "+998901234567")

    await h.press(MOM, "reg:child", name="Мама")
    await h.send(MOM, "Тимур", name="Мама")
    assert "В каком классе учится Тимур" in h.api.last(MOM).text
    await h.send(MOM, "пятый", name="Мама")  # класс — только кнопкой
    assert "кнопкой" in h.api.last(MOM).text
    await h.press(MOM, "reg:grade:5", name="Мама")
    assert "согласие" in h.api.last(MOM).text
    assert "reg:consent" in h.callback_data(h.api.last(MOM))
    await h.press(MOM, "reg:consent", name="Мама")

    card = h.api.last(MOM).text
    assert "Тимур зарегистрирован" in card and "https://edu.example.com/" in card
    login = card.split("Логин: <code>")[1].split("</code>")[0]
    code = card.split("Код: <code>")[1].split("</code>")[0]
    async with SessionLocal() as s:
        kid = await login_code(s, login, code)
        student = await s.get(Student, kid.id)
        assert student.grade == 5 and student.consent_confirmed
        assert [c.user_id for c in await get_children(s, mom.id)] == [kid.id]
        roles = sorted(m.member_role for m in await s.scalars(select(FamilyMember)))
        assert roles == ["parent", "student"]  # ребёнок сразу в семье родителя


async def test_phone_checks(h, adults_only):
    await h.send(TEACHER, "/start", name="Учитель")
    await h.press(TEACHER, "role:teacher", name="Учитель")
    await h.press(TEACHER, "reg:keepname", name="Учитель")  # имя из Telegram
    await _contact(h, TEACHER, "+998901112233", owner=12345, name="Учитель")  # чужой контакт
    assert "собственный номер" in h.api.last(TEACHER).text
    await h.send(TEACHER, "+998901112233", name="Учитель")  # текстом нельзя — не проверить
    assert "собственный номер" in h.api.last(TEACHER).text
    await _contact(h, TEACHER, "+7 999 000 11 22", name="Учитель")
    assert "+998" in h.api.last(TEACHER).text
    async with SessionLocal() as s:
        s.add(User(phone="+998901112233", role="parent"))
        await s.commit()
    await _contact(h, TEACHER, "998901112233", name="Учитель")
    assert "уже привязан" in h.api.last(TEACHER).text
    await h.send(TEACHER, "Пропустить", name="Учитель")
    assert "учитель" in h.api.texts(TEACHER)[-2]
    async with SessionLocal() as s:
        teacher = await get_by_telegram(s, TEACHER)
        assert (teacher.full_name, teacher.phone) == ("Учитель", None)


async def test_teacher_adds_student_without_consent(h, adults_only):
    await h.send(TEACHER, "/start", name="Учитель")
    await h.press(TEACHER, "role:teacher", name="Учитель")
    await h.press(TEACHER, "reg:menu", name="Учитель")
    await h.press(TEACHER, "reg:child", name="Учитель")
    await h.send(TEACHER, "Лола", name="Учитель")
    await h.press(TEACHER, "reg:grade:0", name="Учитель")
    card = h.api.last(TEACHER).text
    assert "Лола добавлен" in card and "согласие родителя" in card
    async with SessionLocal() as s:
        student = await s.scalar(select(Student))
        assert student.grade is None and not student.consent_confirmed


async def test_cancel_and_commands_during_registration(h, adults_only):
    await _register_parent(h, phone=None)
    await h.press(MOM, "reg:child", name="Мама")
    await h.send(MOM, "/menu", name="Мама")  # команда не становится именем ребёнка
    assert "Меню родителя" in h.api.last(MOM).text
    await h.press(MOM, "reg:child", name="Мама")
    await h.send(MOM, "Аня", name="Мама")
    await h.press(MOM, "reg:cancel", name="Мама")
    assert "Отменено" in h.api.last(MOM).text
    await h.press(MOM, "reg:consent", name="Мама")  # старая кнопка после отмены
    async with SessionLocal() as s:
        assert await s.scalar(select(Student)) is None


async def test_student_account_gets_app_link(h, adults_only):
    async with SessionLocal() as s:
        s.add(User(telegram_id=KID, full_name="Тимур", role="student"))
        await s.commit()
    await h.send(KID, "/start", name="Тимур")
    msg = h.api.last(KID)
    assert "приложении EDU" in msg.text
    assert [b.web_app.url for b in h.buttons(msg) if b.web_app] == ["https://edu.example.com/"]
    await h.press(KID, "student:help", name="Тимур")  # уроки в боте выключены
    assert not any("Расскажи" in t for t in h.api.texts(KID))


async def test_evening_reminders_timing(h, adults_only):
    """Ребёнку бот не пишет; родителю — через час после времени ребёнка, не позже 20:30, до 21:00."""
    await _register_parent(h)
    await h.press(MOM, "reg:child", name="Мама")
    await h.send(MOM, "Тимур", name="Мама")
    await h.press(MOM, "reg:grade:3", name="Мама")  # 1–4 классов нет — кнопка из старого сообщения
    assert "reg:grade:5" in h.callback_data(h.api.last(MOM))
    await h.press(MOM, "reg:grade:6", name="Мама")
    await h.press(MOM, "reg:consent", name="Мама")
    today = local_now()

    assert await evening_reminders(h.bot, today.replace(hour=19, minute=5)) == 0  # детям — приложение
    assert await parent_reminders(h.bot, today.replace(hour=19, minute=55)) == 0  # 19:00 + час ещё не прошёл
    assert await parent_reminders(h.bot, today.replace(hour=20, minute=0)) == 1
    assert await parent_reminders(h.bot, today.replace(hour=20, minute=10)) == 0  # раз в день
    await process_events_once(h.bot)
    assert "ещё не прошёл(а) вечерний тест" in h.api.last(MOM).text

    async with SessionLocal() as s:
        student = await s.scalar(select(Student))
        student.evening_time, student.parent_reminded_on = "20:00", None
        await s.commit()
    assert await parent_reminders(h.bot, today.replace(hour=20, minute=25)) == 0
    assert await parent_reminders(h.bot, today.replace(hour=21, minute=5)) == 0  # тихий час
    assert await parent_reminders(h.bot, today.replace(hour=20, minute=30)) == 1  # не позже 20:30
    async with SessionLocal() as s:
        assert await s.scalar(select(Event.type).order_by(Event.id.desc())) == "evening_missed"


async def test_phone_link_from_site(h, adults_only):
    """Сайт → /start phone: взрослый без номера делится им, и коды входа приходят в бот."""
    await _register_parent(h, phone=None)
    await h.send(MOM, "/start phone", name="Мама")
    assert _reply_buttons(h.api.last(MOM))[0].request_contact
    await _contact(h, MOM, "+998 90 555 44 33")
    assert "Номер привязан" in h.api.last(MOM).text  # без повторного «регистрация завершена»
    async with SessionLocal() as s:
        assert (await get_by_telegram(s, MOM)).phone == "+998905554433"

    await h.send(MOM, "/start phone", name="Мама")  # номер уже есть — сразу на сайт
    assert "Номер привязан" in h.api.last(MOM).text


async def test_phone_link_for_newcomer_starts_registration(h, adults_only):
    await h.send(KID, "/start phone", name="Новичок")
    assert "role:parent" in h.callback_data(h.api.last(KID))
