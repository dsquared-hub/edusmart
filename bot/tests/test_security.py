"""Перенесено из обновлённого старого бота: владелец, бан-лист, анти-флуд,
только личные чаты, экранирование HTML, лимит длины темы."""
from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import select

from app.db.models import BlockedUser, Topic
from app.db.session import SessionLocal
from app.repositories.users import get_by_telegram
from bot.middlewares import FloodControlMiddleware
from conftest import OWNER
from test_bot_flow import KID, MOM, TEACHER, _student_with_consent

INTRUDER = 4444


async def test_myid(h):
    await h.send(KID, "/myid")
    assert f"<code>{KID}</code>" in h.api.last(KID).text


async def test_owner_commands_are_owner_only(h):
    for cmd in ("/block 1", "/unblock 1", "/status"):
        await h.send(KID, cmd)
        assert "только для владельца" in h.api.last(KID).text


async def test_block_unblock_and_status(h):
    await h.send(INTRUDER, "/start", name="Хулиган")
    await h.send(OWNER, f"/block {INTRUDER} спам", name="Владелец")
    assert f"Заблокирован: {INTRUDER}" in h.api.last(OWNER).text
    async with SessionLocal() as s:
        row = await s.get(BlockedUser, INTRUDER)
        assert row.reason == "спам"

    # Заблокированный получает одно уведомление, дальше — тишина
    await h.send(INTRUDER, "/start", name="Хулиган")
    assert "заблокирован" in h.api.last(INTRUDER).text
    count = len(h.api.sent(INTRUDER))
    await h.send(INTRUDER, "/start", name="Хулиган")
    assert len(h.api.sent(INTRUDER)) == count

    await h.send(OWNER, f"/block {INTRUDER}", name="Владелец")
    assert "Уже заблокирован" in h.api.last(OWNER).text
    await h.send(OWNER, f"/block {OWNER}", name="Владелец")
    assert "Владельца заблокировать нельзя" in h.api.last(OWNER).text
    await h.send(OWNER, "/block abc", name="Владелец")
    assert "Использование: /block &lt;id&gt;" in h.api.last(OWNER).text

    await h.send(OWNER, "/status", name="Владелец")
    status = h.api.last(OWNER).text
    assert "Заблокировано: 1" in status and "gemini-flash-lite-latest" in status

    await h.send(OWNER, f"/unblock {INTRUDER}", name="Владелец")
    assert f"Разблокирован: {INTRUDER}" in h.api.last(OWNER).text
    await h.send(INTRUDER, "/start", name="Хулиган")
    assert "Кто вы?" in h.api.last(INTRUDER).text


async def test_block_command_while_waiting_topic_is_not_sent_to_gemini(h):
    await h.send(OWNER, "/start", name="Владелец")
    await h.press(OWNER, "role:student", name="Владелец")
    await h.send(OWNER, f"/block {INTRUDER}", name="Владелец")
    assert f"Заблокирован: {INTRUDER}" in h.api.last(OWNER).text


async def test_groups_are_ignored(h):
    await h.send(KID, "/start", chat_type="group")
    assert h.api.sent() == []
    async with SessionLocal() as s:  # даже в БД не попал
        assert await get_by_telegram(s, KID) is None


async def test_topic_too_long(h):
    kid_id = await _student_with_consent(h)
    await h.press(KID, "student:help")
    await h.send(KID, "а" * 501)
    assert "слишком длинная" in h.api.last(KID).text
    async with SessionLocal() as s:
        assert await s.scalar(select(Topic).where(Topic.student_user_id == kid_id)) is None
    await h.send(KID, "дроби")  # всё ещё ждём тему
    assert "Объясняю тему: дроби" in h.api.last(KID).text


async def test_names_are_html_escaped(h):
    await _student_with_consent(h)
    await h.send(TEACHER, "/start", name="Учитель")
    await h.press(TEACHER, "role:teacher", name="Учитель")
    await h.press(TEACHER, "access:new", name="Учитель")
    await h.send(TEACHER, "<b>Вася</b> & Co", name="Учитель")
    assert "&lt;b&gt;Вася&lt;/b&gt; &amp; Co" in h.api.last(TEACHER).text
    await h.press(TEACHER, "reg:grade:7", name="Учитель")
    assert "&lt;b&gt;Вася&lt;/b&gt; &amp; Co" in h.api.last(TEACHER).text
    await h.send(TEACHER, "/class", name="Учитель")
    assert "&lt;b&gt;Вася" in h.api.last(TEACHER).text
    await h.send(MOM, "/profile", name="<i>Мама</i>")
    assert "<i>" not in h.api.last(MOM).text


async def test_flood_control_drops_and_warns_once():
    calls, sent = [], []

    class FakeBot:
        async def send_message(self, chat_id, text, **kwargs):
            sent.append(text)

    flood = FloodControlMiddleware(max_messages=3, window_seconds=60)
    user = SimpleNamespace(id=1)
    chat = SimpleNamespace(id=1, type="private")
    event = SimpleNamespace(from_user=user, chat=chat)

    async def handler(event, data):
        calls.append(1)

    for _ in range(6):
        await flood(handler, event, {"bot": FakeBot()})
    assert len(calls) == 3
    assert len(sent) == 1  # предупреждение одно, без спама в ответ


async def test_warnings_right_after_system_boot(monkeypatch):
    """monotonic() считает от старта системы: на свежем сервере он меньше
    интервала уведомлений, но первое уведомление всё равно должно уйти."""
    import bot.middlewares as mw

    monkeypatch.setattr(mw.time, "monotonic", lambda: 1.0)
    sent = []

    class FakeBot:
        async def send_message(self, chat_id, text, **kwargs):
            sent.append(text)

    class Blocked:
        def is_blocked(self, telegram_id):
            return True

    async def handler(event, data):
        raise AssertionError("заблокированный не должен доходить до хендлера")

    event = SimpleNamespace(from_user=SimpleNamespace(id=7, language_code="ru"),
                            chat=SimpleNamespace(id=7, type="private"))
    security = mw.SecurityMiddleware(notify_interval=300)
    for _ in range(2):
        await security(handler, event, {"bot": FakeBot(), "security": Blocked()})
    assert len(sent) == 1

    flood = FloodControlMiddleware(max_messages=1, window_seconds=60)
    for _ in range(3):
        await flood(lambda e, d: _noop(), event, {"bot": FakeBot()})
    assert len(sent) == 2  # и предупреждение о флуде тоже пришло


async def _noop():
    return None
