"""Бот: подтверждение входа на сайт (/start login_<токен>)."""
from __future__ import annotations

from app.db.session import SessionLocal
from app.services import bot_login

USER = 4242


async def _started():
    async with SessionLocal() as s:
        return await bot_login.start(s)


async def test_confirm_login_by_matching_number(h):
    started = await _started()
    await h.send(USER, f"/start login_{started.token}", name="Тимур")
    prompt = h.api.last(USER)
    assert "Вход на сайт" in prompt.text
    data = h.callback_data(prompt)
    assert len(data) == 4 and data[-1].endswith(":x")
    right = next(d for d in data if d.endswith(f":{started.match_code}"))

    await h.press(USER, right, name="Тимур")
    assert "Вход подтверждён" in h.api.texts(USER)[-2]
    # роли ещё нет — сразу предлагаем выбрать
    assert "role:student" in h.callback_data(h.api.last(USER))

    async with SessionLocal() as s:
        status, user = await bot_login.poll(s, started.token)
    assert status == "ok" and user.telegram_id == USER


async def test_wrong_number_cancels_and_link_is_single_use(h):
    started = await _started()
    await h.send(USER, f"/start login_{started.token}")
    data = h.callback_data(h.api.last(USER))
    wrong = next(d for d in data[:-1] if not d.endswith(f":{started.match_code}"))
    await h.press(USER, wrong)
    assert "Число не совпало" in h.api.last(USER).text

    await h.press(USER, data[0])  # повторное нажатие — запрос уже отменён
    assert "устарела" in h.api.last(USER).text
    await h.send(USER, f"/start login_{started.token}")
    assert "устарела" in h.api.last(USER).text


async def test_mentor_login_sets_role_without_role_menu(h):
    async with SessionLocal() as s:
        started = await bot_login.start(s, as_role="teacher")
    await h.send(USER, f"/start login_{started.token}", name="Ментор")
    right = next(d for d in h.callback_data(h.api.last(USER)) if d.endswith(f":{started.match_code}"))
    await h.press(USER, right, name="Ментор")
    assert "Вход подтверждён" in h.api.last(USER).text  # роль уже есть — меню ролей не нужно

    async with SessionLocal() as s:
        status, user = await bot_login.poll(s, started.token)
    assert status == "ok" and user.role == "teacher"


async def test_mentor_login_refuses_student(h):
    await h.send(USER, "/start")
    await h.press(USER, "role:student")
    async with SessionLocal() as s:
        started = await bot_login.start(s, as_role="teacher")
    await h.send(USER, f"/start login_{started.token}")
    right = next(d for d in h.callback_data(h.api.last(USER)) if d.endswith(f":{started.match_code}"))
    await h.press(USER, right)
    assert "вход для менторов" in h.api.last(USER).text


async def test_plain_start_still_works(h):
    await h.send(USER, "/start")
    assert "Кто ты?" in h.api.last(USER).text
