"""Бот для взрослых: регистрация родителя/учителя и ребёнка; ребёнку — ссылка на приложение."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.timeutil import local_now
from app.db.models import Event, FamilyMember, Student, User
from app.db.session import SessionLocal
from app.repositories.students import get_children
from app.repositories.users import get_by_telegram
from app.services.accounts import AccountError, login_code
from bot.events_worker import process_events_once
from bot.scheduler import evening_reminders, parent_reminders

MOM, TEACHER, KID = 7001, 7002, 7003


@pytest.fixture
def adults_only(monkeypatch):
    monkeypatch.setattr(get_settings(), "bot_student_lessons", False)


def _reply_buttons(request) -> list:
    markup = getattr(request, "reply_markup", None)
    return [b for row in getattr(markup, "keyboard", None) or [] for b in row]


def _site_access(text: str) -> tuple[str, str]:
    return text.split("Логин: <code>")[1].split("</code>")[0], text.split("Код: <code>")[1].split("</code>")[0]


async def _register_parent(h, phone: str = "+998 90 123 45 67") -> None:
    await h.send(MOM, "/start", name="Малика Юсупова")
    await h.press(MOM, "role:parent", name="Малика Юсупова")
    await h.contact(MOM, phone, name="Малика Юсупова")


async def test_start_offers_parent_and_teacher(h, adults_only):
    await h.send(KID, "/start", name="Тимур")
    msg = h.api.last(KID)
    assert "Кто вы" in msg.text and "https://edu.example.com/" in msg.text
    assert h.callback_data(msg) == ["role:parent", "role:teacher", "lang:menu"]
    await h.press(KID, "role:student", name="Тимур")  # старая кнопка
    assert "приложении EDU PROGRESSUZ" in h.api.alerts()[-1]

    await h.press(KID, "role:teacher", name="Тимур")
    ask = h.api.last(KID)
    assert "Регистрация учителя" in ask.text
    buttons = _reply_buttons(ask)
    assert len(buttons) == 1 and buttons[0].request_contact  # только «Отправить номер»
    async with SessionLocal() as s:
        assert (await get_by_telegram(s, KID)).role is None  # роль — только вместе с номером


async def test_deep_links_open_registration(h, adults_only):
    await h.send(MOM, "/start parent", name="Мама")
    assert "Регистрация родителя" in h.api.last(MOM).text
    await h.send(TEACHER, "/start teacher", name="Учитель")
    assert "Регистрация учителя" in h.api.last(TEACHER).text
    await h.contact(TEACHER, "+998901112233", name="Учитель")
    async with SessionLocal() as s:
        assert (await get_by_telegram(s, TEACHER)).role == "teacher"
    await h.send(TEACHER, "/start parent", name="Учитель")  # уже зарегистрирован — просто меню
    assert "Кабинет учителя" in h.api.last(TEACHER).text


async def test_parent_registers_by_phone_then_child_by_name(h, adults_only):
    await _register_parent(h)
    texts = h.api.texts(MOM)
    assert "Готово, Малика Юсупова" in texts[-3]
    assert "Ваш вход на сайт (родитель)" in texts[-2] and "не</b> вход ребёнка" in texts[-2]
    assert "Как зовут ребёнка" in texts[-1] and "соглашаетесь" in texts[-1]
    async with SessionLocal() as s:
        mom = await get_by_telegram(s, MOM)
        assert (mom.role, mom.full_name, mom.phone) == ("parent", "Малика Юсупова", "+998901234567")

    await h.send(MOM, "Тимур", name="Мама")  # имя — и сразу профиль с кодом
    card = h.api.last(MOM).text
    assert "Тимур зарегистрирован" in card and "https://edu.example.com/" in card
    login, code = _site_access(card)
    async with SessionLocal() as s:
        kid = await login_code(s, login, code)
        student = await s.get(Student, kid.id)
        assert kid.role == "student" and student.grade is None and student.consent_confirmed
        assert [c.user_id for c in await get_children(s, mom.id)] == [kid.id]
        roles = sorted(m.member_role for m in await s.scalars(select(FamilyMember)))
        assert roles == ["parent", "student"]  # ребёнок сразу в семье родителя

    await h.press(MOM, "reg:child", name="Мама")  # «Зарегистрировать ещё одного»
    await h.send(MOM, "Аня", name="Мама")
    assert "Аня зарегистрирован" in h.api.last(MOM).text


async def test_teacher_registration_is_separate(h, adults_only):
    await h.send(TEACHER, "/start", name="Учитель")
    await h.press(TEACHER, "role:teacher", name="Учитель")
    await h.contact(TEACHER, "+998901112233", name="Учитель")
    texts = h.api.texts(TEACHER)
    assert "учитель" in texts[-3] and "кабинет учителя" in texts[-2]
    assert "Кабинет учителя" in texts[-1]  # ребёнка не спрашиваем — сразу меню
    login, code = _site_access(texts[-2])
    async with SessionLocal() as s:
        assert (await login_code(s, login, code)).role == "teacher"

    await h.press(TEACHER, "reg:child", name="Учитель")
    await h.send(TEACHER, "Лола", name="Учитель")
    card = h.api.last(TEACHER).text
    assert "Лола добавлен" in card and "согласие родителя" in card
    async with SessionLocal() as s:
        student = await s.scalar(select(Student))
        assert student.grade is None and not student.consent_confirmed


async def test_student_account_in_bot_can_register_as_parent(h, adults_only):
    """Тот, кто раньше был «учеником» в боте, видит регистрацию, а не ссылку на приложение."""
    async with SessionLocal() as s:
        s.add(User(telegram_id=MOM, full_name="Малика", role="student"))
        await s.commit()
    await h.send(MOM, "/start", name="Малика")
    assert "role:parent" in h.callback_data(h.api.last(MOM))
    await h.press(MOM, "role:parent", name="Малика")
    await h.contact(MOM, "901234567", name="Малика")
    async with SessionLocal() as s:
        assert (await get_by_telegram(s, MOM)).role == "parent"
    assert "Как зовут ребёнка" in h.api.last(MOM).text


async def test_phone_checks(h, adults_only):
    await h.send(TEACHER, "/start", name="Учитель")
    await h.contact(TEACHER, "+998901112233", name="Учитель")  # номер без выбора роли
    assert "Кто вы" in h.api.last(TEACHER).text
    await h.press(TEACHER, "role:teacher", name="Учитель")
    await h.contact(TEACHER, "+998901112233", owner=12345, name="Учитель")  # чужой контакт
    assert "собственный номер" in h.api.last(TEACHER).text
    await h.contact(TEACHER, "+7 999 000 11 22", name="Учитель")
    assert "+998" in h.api.last(TEACHER).text
    async with SessionLocal() as s:
        s.add(User(phone="+998901112233", role="parent"))
        await s.commit()
    await h.contact(TEACHER, "998901112233", name="Учитель")
    assert "уже привязан" in h.api.last(TEACHER).text
    async with SessionLocal() as s:
        assert (await get_by_telegram(s, TEACHER)).role is None  # не зарегистрирован


async def test_adult_gets_new_site_code_from_menu(h, adults_only):
    await _register_parent(h)
    login, code = _site_access(h.api.texts(MOM)[-2])
    async with SessionLocal() as s:
        mom = await login_code(s, login, code)
        assert (mom.telegram_id, mom.role) == (MOM, "parent")

    # Забыл код — кнопка в меню даёт новый, логин тот же, старый код больше не подходит
    await h.send(MOM, "/menu", name="Мама")
    assert "site:access" in h.callback_data(h.api.last(MOM))
    await h.press(MOM, "site:access", name="Мама")
    login2, code2 = _site_access(h.api.last(MOM).text)
    assert login2 == login
    async with SessionLocal() as s:
        assert (await login_code(s, login, code2)).id == mom.id
        if code2 != code:
            with pytest.raises(AccountError):
                await login_code(s, login, code)


async def test_site_access_only_for_adults(h, adults_only):
    await h.send(KID, "/start", name="Тимур")  # не зарегистрирован
    await h.press(KID, "site:access", name="Тимур")
    assert h.api.alerts()
    async with SessionLocal() as s:
        assert (await get_by_telegram(s, KID)).login is None


async def test_cancel_and_commands_during_registration(h, adults_only):
    await _register_parent(h)
    await h.send(MOM, "/menu", name="Мама")  # команда не становится именем ребёнка
    assert "Кабинет родителя" in h.api.last(MOM).text
    await h.press(MOM, "reg:child", name="Мама")
    await h.press(MOM, "reg:cancel", name="Мама")
    assert "Отменено" in h.api.last(MOM).text
    await h.send(MOM, "Аня", name="Мама")  # после отмены имя не принимается
    await h.press(MOM, "reg:consent", name="Мама")  # кнопка прежней регистрации — просто меню
    assert "Кабинет родителя" in h.api.last(MOM).text
    await h.press(MOM, "role:teacher", name="Мама")  # старая кнопка роли — роль не меняется
    async with SessionLocal() as s:
        assert await s.scalar(select(Student)) is None
        assert (await get_by_telegram(s, MOM)).role == "parent"


async def test_registered_adult_changes_phone(h, adults_only):
    await _register_parent(h)
    await h.send(MOM, "/menu", name="Мама")
    await h.contact(MOM, "+998 90 000 00 01")
    assert "Номер сохранён" in h.api.texts(MOM)[-2]
    async with SessionLocal() as s:
        mom = await get_by_telegram(s, MOM)
        assert (mom.role, mom.phone) == ("parent", "+998900000001")


async def test_parent_and_teacher_cabinets(h, adults_only):
    await _register_parent(h)
    await h.send(MOM, "/menu", name="Мама")
    cabinet = h.api.last(MOM).text
    assert "Кабинет родителя" in cabinet and "Детей пока нет" in cabinet
    await h.press(MOM, "reg:child", name="Мама")
    await h.send(MOM, "Тимур", name="Мама")
    await h.send(MOM, "/menu", name="Мама")
    cabinet = h.api.last(MOM).text
    assert "<b>Тимур</b>" in cabinet and "Вечерний тест: сегодня ещё не проходил(а)" in cabinet
    assert "ещё не заходил(а)" in cabinet
    assert "cabinet:refresh" in h.callback_data(h.api.last(MOM))
    await h.press(MOM, "cabinet:refresh", name="Мама")
    assert "<b>Тимур</b>" in h.api.last(MOM).text

    await h.send(TEACHER, "/start teacher", name="Учитель")
    await h.contact(TEACHER, "+998901112233", name="Учитель")
    assert "Кабинет учителя" in h.api.last(TEACHER).text and "Учеников пока нет" in h.api.last(TEACHER).text
    await h.press(TEACHER, "reg:child", name="Учитель")
    await h.send(TEACHER, "Лола", name="Учитель")
    await h.send(TEACHER, "/menu", name="Учитель")
    assert "👥 Учеников: 1" in h.api.last(TEACHER).text
    assert "Тимур" not in h.api.last(TEACHER).text  # чужой ребёнок в кабинет учителя не попадает


async def test_evening_reminders_timing(h, adults_only):
    """Ребёнку бот не пишет; родителю — через час после времени ребёнка, не позже 20:30, до 21:00."""
    await _register_parent(h)
    await h.send(MOM, "Тимур", name="Мама")
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


async def test_parent_day_message_in_bot(h, adults_only):
    """16:30: родителю — неделя 🟢/🔴 и тревога, если ребёнок не занимается 2+ дня."""
    from app.repositories import events as events_repo
    from app.services.parent_day import EVENT_PARENT_DAY

    await _register_parent(h)
    await h.send(MOM, "Тимур", name="Мама")
    async with SessionLocal() as s:
        kid = await s.scalar(select(Student))
        await events_repo.enqueue(s, EVENT_PARENT_DAY, {"student_user_id": kid.user_id, "missed_days": 3, "week": "🟢🔴🔴🔴⏳"})
        await s.commit()
    await process_events_once(h.bot)
    text = h.api.last(MOM).text
    assert "Тимур не занимается уже 3 дн." in text and "17:00" in text and "🟢🔴🔴🔴⏳" in text
    await h.send(MOM, "/menu", name="Мама")
    assert "📅 Неделя:" in h.api.last(MOM).text  # и в кабинете родителя
