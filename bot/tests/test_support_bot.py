"""Бот: поддержка для родителя и учителя, ответ владельца."""
from __future__ import annotations

from conftest import OWNER
from test_bot_flow import KID, MOM, TEACHER


async def _parent(h) -> None:
    await h.send(MOM, "/start", name="Мама")
    await h.press(MOM, "role:parent", name="Мама")
    await h.press(MOM, "reg:menu", name="Мама")  # регистрацию можно дозаполнить позже


async def _ask(h, uid: int, text: str | None = None, **kw) -> None:
    await h.press(uid, "support:new", name="Мама")
    await h.send(uid, text, name="Мама", **kw)


async def test_parent_asks_and_owner_replies(h):
    await _parent(h)
    assert "support:new" in h.callback_data(h.api.last(MOM))

    await h.press(MOM, "support:new", name="Мама")
    assert "Поддержка" in h.api.last(MOM).text
    assert h.callback_data(h.api.last(MOM)) == ["support:cancel"]
    await h.send(MOM, "Не приходит <b>отчёт</b>", name="Мама")
    assert "Обращение #1 отправлено" in h.api.last(MOM).text

    card = h.api.last(OWNER)
    assert "Обращение #1" in card.text and "Мама" in card.text and str(MOM) in card.text
    assert "&lt;b&gt;отчёт&lt;/b&gt;" in card.text  # текст пользователя экранирован
    assert h.callback_data(card) == ["sup:reply:1"]

    await h.press(OWNER, "sup:reply:1", name="Владелец")
    await h.send(OWNER, "Проверили — отчёт приходит по воскресеньям", name="Владелец")
    assert "Ответ на #1 отправлен" in h.api.last(OWNER).text
    reply = h.api.last(MOM).text
    assert "Ответ поддержки" in reply and "по воскресеньям" in reply

    # повторный ответ на то же обращение не уйдёт
    await h.press(OWNER, "sup:reply:1", name="Владелец")
    await h.send(OWNER, "ещё раз", name="Владелец")
    assert "уже ответили" in h.api.last(OWNER).text


async def test_teacher_has_support_and_screenshot_is_copied(h):
    await h.send(TEACHER, "/start", name="Учитель")
    await h.press(TEACHER, "role:teacher", name="Учитель")
    await h.press(TEACHER, "reg:menu", name="Учитель")
    assert "support:new" in h.callback_data(h.api.last(TEACHER))

    await h.send(TEACHER, "/support", name="Учитель")
    await h.send(TEACHER, photo=True, caption="Ошибка на экране", name="Учитель")
    assert "отправлено" in h.api.last(TEACHER).text
    copies = [r for r in h.api.requests if type(r).__name__ == "CopyMessage"]
    assert len(copies) == 1 and copies[0].chat_id == OWNER


async def test_validation_cancel_and_limit(h):
    await _parent(h)
    await _ask(h, MOM, photo=True)  # скриншот без подписи
    assert "текстом" in h.api.last(MOM).text
    await h.press(MOM, "support:cancel", name="Мама")
    assert "отменено" in h.api.last(MOM).text
    await h.send(MOM, "это уже не вопрос", name="Мама")
    assert not [r for r in h.api.sent(OWNER) if "Обращение" in (r.text or "")]

    for n in range(5):
        await _ask(h, MOM, f"вопрос {n}")
    await _ask(h, MOM, "шестой")
    assert "За сутки уже отправлено 5" in h.api.last(MOM).text


async def test_only_adults_and_only_owner_replies(h):
    await h.send(KID, "/start")
    await h.press(KID, "role:student")
    await h.send(KID, "/support")
    assert "для родителей и учителей" in h.api.last(KID).text

    await _parent(h)
    await _ask(h, MOM, "вопрос")
    await h.press(MOM, "sup:reply:1", name="Мама")  # не владелец
    assert "недоступно" in h.api.alerts()[-1]


async def test_owner_lists_open_tickets(h):
    await h.send(OWNER, "/support", name="Владелец")
    assert "Открытых обращений нет" in h.api.last(OWNER).text
    await _parent(h)
    await _ask(h, MOM, "первый")
    await _ask(h, MOM, "второй")
    await h.send(OWNER, "/support", name="Владелец")
    cards = [r for r in h.api.sent(OWNER) if "sup:reply:" in "".join(h.callback_data(r))]
    assert [h.callback_data(c) for c in cards[-2:]] == [["sup:reply:1"], ["sup:reply:2"]]


async def test_ticket_from_site_reaches_owner_and_reply_is_saved(h):
    """Обращение с сайта: карточка владельцу из очереди, ответ пользователю без Telegram — на сайт."""
    from app.db.session import SessionLocal
    from app.services import support
    from app.services.accounts import create_child_access
    from app.repositories.users import get_by_telegram
    from bot.events_worker import process_events_once

    await _parent(h)
    async with SessionLocal() as s:
        mom = await get_by_telegram(s, MOM)
        ticket = await support.create_ticket(s, mom, "вопрос с сайта", notify_owner=True)
    await process_events_once(h.bot)
    card = h.api.last(OWNER)
    assert "вопрос с сайта" in card.text and "Отправлено с сайта" in card.text
    assert h.callback_data(card) == [f"sup:reply:{ticket.id}"]

    # родитель без Telegram (вход по логину и коду) — ответ сохраняется для сайта
    async with SessionLocal() as s:
        mom = await get_by_telegram(s, MOM)
        child = await create_child_access(s, mom, "Тимур", grade=5)
        child.user.role = "parent"  # для проверки: пользователь без telegram_id
        await s.commit()
        no_tg = await support.create_ticket(s, child.user, "без телеграма")
    await h.press(OWNER, f"sup:reply:{no_tg.id}", name="Владелец")
    await h.send(OWNER, "ответ", name="Владелец")
    assert "увидит ответ на сайте" in h.api.last(OWNER).text
