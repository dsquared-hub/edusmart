"""Сквозные сценарии бота поверх общих сервисов /backend."""
from __future__ import annotations

from sqlalchemy import select

from app.db.models import Topic
from app.db.session import SessionLocal
from app.repositories.students import get_student
from app.repositories.users import get_by_telegram
from app.services.accounts import login_code
from bot.events_worker import process_events_once
from bot.scheduler import three_day_nudge, weekly_report

KID, MOM, TEACHER = 111, 222, 333
CORRECT = [0, 1, 1, 2]  # правильные ответы демо-объяснения (gemini_stub)


async def _student_with_consent(h) -> int:
    """Ученик + родитель, который привязался по коду и дал согласие."""
    await h.send(KID, "/start")
    await h.press(KID, "role:student")
    async with SessionLocal() as s:
        kid = await get_by_telegram(s, KID)
        code = (await get_student(s, kid.id)).family_code
    await h.send(MOM, "/start", name="Мама")
    await h.press(MOM, "role:parent", name="Мама")
    await h.press(MOM, "parent:bind", name="Мама")
    await h.send(MOM, code, name="Мама")
    await h.press(MOM, "consent:confirm", name="Мама")
    return kid.id


async def _topic(kid_id: int) -> Topic:
    async with SessionLocal() as s:
        return await s.scalar(
            select(Topic).where(Topic.student_user_id == kid_id).order_by(Topic.id.desc())
        )


async def test_start_shows_roles(h):
    await h.send(KID, "/start")
    assert "Кто вы?" in h.api.last(KID).text
    assert h.callback_data(h.api.last(KID)) == [
        "role:parent", "role:teacher", "role:student", "lang:menu"  # ученик — только в старом режиме
    ]


async def test_consent_required_before_explaining(h):
    await h.send(KID, "/start")
    await h.press(KID, "role:student")
    await h.press(KID, "student:help")
    assert "не подтвердил согласие" in h.api.last(KID).text


async def test_full_topic_flow_and_parent_notification(h):
    kid_id = await _student_with_consent(h)
    assert "Согласие подтверждено" in h.api.last(MOM).text

    await h.press(KID, "student:help")
    assert "Расскажи, что не понял" in h.api.last(KID).text
    await h.send(KID, "дроби")
    # 1) Сначала объяснение всей темы — без вопросов
    lesson = h.api.last(KID)
    assert "Объясняю тему: дроби" in lesson.text
    assert "Дробь — это часть целого" in lesson.text and "Сравниваем дроби" in lesson.text
    assert "Какая это дробь?" not in lesson.text
    topic = await _topic(kid_id)
    assert topic.source == "bot" and topic.status == "in_progress"
    assert f"quiz:{topic.id}" in h.callback_data(lesson)

    # 2) «Понятно, к вопросам» → первый вопрос
    await h.press(KID, f"quiz:{topic.id}")
    question = h.api.last(KID)
    assert "Вопрос 1 из 4" in question.text and "Какая это дробь?" in question.text
    assert f"ans:{topic.id}:0:0" in h.callback_data(question)
    assert f"lesson:{topic.id}" in h.callback_data(question)
    # Mini App-кнопка «Открыть на сайте» на ту же тему
    urls = [b.web_app.url for b in h.buttons(question) if b.web_app]
    assert urls == [f"https://edu.example.com/learn/{topic.id}"]

    # 3) Неверно → разбор выбранного варианта и верный ответ, дальше — следующий вопрос
    await h.press(KID, f"ans:{topic.id}:0:1")
    assert "Не совсем" in h.api.alerts()[-1]
    review = h.api.last(KID)
    assert "Ты выбрал: <b>8/3</b>" in review.text
    assert "Числа перепутаны" in review.text  # почему выбранный вариант неверный
    assert "Правильный ответ: <b>3/8</b>" in review.text
    assert h.callback_data(review) == [f"quiz:{topic.id}", f"rep:{topic.id}:0"]

    # Верный ответ → тоже разбор: почему это правильно
    for step in range(1, 4):
        await h.press(KID, f"quiz:{topic.id}")
        assert f"Вопрос {step + 1} из 4" in h.api.last(KID).text
        await h.press(KID, f"ans:{topic.id}:{step}:{CORRECT[step]}")
    review = h.api.texts(KID)[-2]
    assert "Верно! +10 очков" in review and "Ты выбрал: <b>4/7</b>" in review
    assert "4 куска больше 2" in review and "Правильный ответ" not in review

    assert "Тема закрыта" in h.api.last(KID).text
    topic = await _topic(kid_id)
    # шаг 1 — ошибка (0), остальные с первой попытки (+10)
    assert topic.status == "completed" and topic.points_earned == 30
    async with SessionLocal() as s:
        student = await get_student(s, kid_id)
        assert student.points == 30 and student.streak == 1

    # Событие из очереди → сообщение родителю
    assert await process_events_once(h.bot) == 1
    assert "закрыл(а) тему «дроби»" in h.api.last(MOM).text
    assert await process_events_once(h.bot) == 0


async def test_teacher_notified_when_topic_completed(h):
    kid_id = await _student_with_consent(h)
    async with SessionLocal() as s:
        code = (await get_student(s, kid_id)).family_code
    await h.send(TEACHER, "/start", name="Учитель")
    await h.press(TEACHER, "role:teacher", name="Учитель")
    await h.press(TEACHER, "teacher:bind", name="Учитель")
    await h.send(TEACHER, code, name="Учитель")

    await h.press(KID, "student:help")
    await h.send(KID, "дроби")
    topic = await _topic(kid_id)
    for step in range(4):
        await h.press(KID, f"quiz:{topic.id}")
        await h.press(KID, f"ans:{topic.id}:{step}:{CORRECT[step]}")
    assert "Тема закрыта" in h.api.last(KID).text

    assert await process_events_once(h.bot) == 1
    text = h.api.last(TEACHER).text
    assert "закрыл(а) тему «дроби»" in text
    assert "Вопросов: 4" in text and "+40 очков" in text
    assert "закрыл(а) тему «дроби»" in h.api.last(MOM).text


async def test_photo_is_accepted_and_not_stored(h):
    kid_id = await _student_with_consent(h)
    await h.press(KID, "student:help")
    await h.send(KID, photo=True)
    assert "Объясняю тему" in h.api.last(KID).text
    topic = await _topic(kid_id)
    assert topic.title == "Фото задания"
    assert "jpeg" not in str(topic.steps)


async def test_daily_limit_is_shared_with_site(h, settings):
    kid_id = await _student_with_consent(h)
    h.explain.settings = settings.model_copy(update={"daily_explain_limit": 1})
    async with SessionLocal() as s:  # объяснение, запрошенное на сайте
        await h.explain.start(s, kid_id, "проценты", source="web")
    await h.press(KID, "student:help")
    assert "лимит объяснений закончился (1)" in h.api.last(KID).text


async def test_continue_on_bot_after_site_and_stale_button(h):
    kid_id = await _student_with_consent(h)
    async with SessionLocal() as s:
        topic = await h.explain.start(s, kid_id, "дроби", source="web")
    # Главное меню предлагает продолжить тему, начатую на сайте
    await h.send(KID, "/menu")
    assert f"resume:{topic.id}" in h.callback_data(h.api.last(KID))
    await h.press(KID, f"resume:{topic.id}")
    assert "Объясняю тему" in h.api.last(KID).text  # ещё ни одного ответа — с объяснения

    # На сайте ученик прошёл шаг 1 — старая кнопка в боте не засчитывается
    async with SessionLocal() as s:
        await h.explain.answer(s, kid_id, topic.id, 0, CORRECT[0])
    await h.press(KID, f"ans:{topic.id}:0:0")
    texts = h.api.texts(KID)
    assert "уже продвинулся" in texts[-2]
    assert "Вопрос 2 из 4" in texts[-1]
    async with SessionLocal() as s:
        assert (await get_student(s, kid_id)).points == 10

    # Продолжение с середины — сразу текущий вопрос, объяснение по кнопке
    await h.press(KID, f"resume:{topic.id}")
    assert "Вопрос 2 из 4" in h.api.last(KID).text
    await h.press(KID, f"lesson:{topic.id}")
    assert "Объясняю тему" in h.api.last(KID).text
    assert f"quiz:{topic.id}" in h.callback_data(h.api.last(KID))


async def test_old_topic_without_explanations(h):
    """Темы, созданные до пояснений к вариантам: разбор всё равно показывается."""
    kid_id = await _student_with_consent(h)
    async with SessionLocal() as s:
        topic = await h.explain.start(s, kid_id, "дроби", source="bot")
        steps = [{k: v for k, v in step.items() if k != "explanations"} for step in topic.steps]
        topic.steps = steps
        await s.commit()
    await h.press(KID, f"ans:{topic.id}:0:2")
    review = h.api.last(KID).text
    assert "Ты выбрал: <b>3/5</b>" in review and "Правильный ответ: <b>3/8</b>" in review
    assert "Представь пиццу" in review  # напоминание о шаге вместо пояснения


async def test_questions_of_closed_topic(h):
    kid_id = await _student_with_consent(h)
    async with SessionLocal() as s:
        topic = await h.explain.start(s, kid_id, "дроби", source="bot")
        for step, option in enumerate(CORRECT):
            await h.explain.answer(s, kid_id, topic.id, step, option)
    await h.press(KID, f"quiz:{topic.id}")
    assert "уже закрыта" in h.api.alerts()[-1]


async def test_pause_keeps_topic(h):
    kid_id = await _student_with_consent(h)
    await h.press(KID, "student:help")
    await h.send(KID, "дроби")
    topic = await _topic(kid_id)
    await h.press(KID, f"pause:{topic.id}")
    assert "на паузе" in h.api.last(KID).text
    assert (await _topic(kid_id)).status == "in_progress"


async def test_parent_creates_login_without_telegram(h):
    await _student_with_consent(h)
    await h.press(MOM, "access:new", name="Мама")  # кнопка из старых сообщений ведёт в регистрацию
    await h.send(MOM, "Тимур", name="Мама")
    await h.press(MOM, "reg:grade:5", name="Мама")
    await h.press(MOM, "reg:consent", name="Мама")
    text = h.api.last(MOM).text
    assert "Логин" in text and "Код" in text
    login = text.split("Логин: <code>")[1].split("</code>")[0]
    code = text.split("Код: <code>")[1].split("</code>")[0]
    assert login.startswith("timur")
    async with SessionLocal() as s:
        user = await login_code(s, login, code)
        student = await get_student(s, user.id)
        assert student.consent_confirmed  # создал родитель — согласие есть
    # В профиле родителя — кнопка нового кода
    await h.press(MOM, "parent:profile", name="Мама")
    assert f"newcode:{user.id}" in h.callback_data(h.api.last(MOM))
    await h.press(MOM, f"newcode:{user.id}", name="Мама")
    assert "Старый код больше не работает" in h.api.last(MOM).text


async def test_teacher_class_and_student_access(h):
    await _student_with_consent(h)
    await h.send(TEACHER, "/start", name="Учитель")
    await h.press(TEACHER, "role:teacher", name="Учитель")
    await h.press(TEACHER, "access:new", name="Учитель")
    await h.send(TEACHER, "Лола Каримова", name="Учитель")
    await h.press(TEACHER, "reg:grade:0", name="Учитель")
    assert "согласие родителя" in h.api.last(TEACHER).text
    await h.send(TEACHER, "/class", name="Учитель")
    assert "Лола Каримова" in h.api.last(TEACHER).text


async def test_profile_and_scheduler_jobs(h):
    await _student_with_consent(h)
    await h.send(KID, "/profile")
    assert "Твой профиль" in h.api.last(KID).text
    await weekly_report(h.bot)
    assert "Еженедельный отчёт" in h.api.last(MOM).text
    await three_day_nudge(h.bot)  # никто не пропадал — без ошибок


async def test_outdated_consent_shown_in_menu(h):
    """Сменили POLICY_VERSION — бот сразу показывает «ждём согласия», как сайт и API."""
    kid_id = await _student_with_consent(h)
    await h.send(KID, "/start")
    assert "Ждём согласия" not in h.api.last(KID).text
    async with SessionLocal() as s:
        (await get_student(s, kid_id)).consent_version = "old-policy"
        await s.commit()
    await h.send(KID, "/start")
    assert "Ждём согласия" in h.api.last(KID).text
