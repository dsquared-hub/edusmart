"""Вход на сайт через бота: ссылка → число в боте → сайт получает токен."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.core.timeutil import utcnow
from app.db.models import LoginRequest
from app.db.session import SessionLocal
from app.repositories.blocks import block_user
from app.services import bot_login
from app.repositories.users import get_by_telegram, upsert_telegram_user
from test_api import KID_TG, login, make_student, widget_payload


async def _start(client) -> dict:
    r = await client.post("/api/auth/bot/start")
    assert r.status_code == 200, r.text
    return r.json()


async def _answer(started: dict, tg_id: int, chosen: int | None) -> str:
    async with SessionLocal() as s:
        request = await bot_login.find_pending(s, started["token"])
        user = await get_by_telegram(s, tg_id)
        return await bot_login.answer(s, request.id, user, chosen)


async def test_bot_login_flow(client):
    user_id = await make_student()
    started = await _start(client)
    assert started["url"] == f"https://t.me/edu_test_bot?start=login_{started['token']}"
    assert len(started["url"].split("start=")[1]) <= 64  # лимит deep link Telegram
    assert 10 <= started["code"] <= 99 and started["expires_in"] == 300

    poll = {"token": started["token"]}
    r = await client.post("/api/auth/bot/poll", json=poll)
    assert r.status_code == 202 and r.json() == {"status": "pending"}

    assert await _answer(started, KID_TG, started["code"]) == "confirmed"
    r = await client.post("/api/auth/bot/poll", json=poll)
    assert r.status_code == 200, r.text
    assert r.json()["me"]["id"] == user_id
    me = await client.get("/api/me", headers={"Authorization": f"Bearer {r.json()['token']}"})
    assert me.status_code == 200

    # Второй раз тот же запрос не сработает
    r = await client.post("/api/auth/bot/poll", json=poll)
    assert r.status_code == 410 and r.json()["detail"]["code"] == "bot_login_expired"


async def test_token_not_stored_in_plain_text(client):
    started = await _start(client)
    async with SessionLocal() as s:
        row = await s.scalar(select(LoginRequest))
    assert started["token"] not in row.token_hash and len(row.token_hash) == 64


async def test_wrong_number_or_not_me_cancels(client):
    await make_student()
    started = await _start(client)
    wrong = started["code"] + 1 if started["code"] < 99 else 10
    assert await _answer(started, KID_TG, wrong) == "wrong_code"
    r = await client.post("/api/auth/bot/poll", json={"token": started["token"]})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "bot_login_rejected"
    # после отмены число уже не подобрать
    async with SessionLocal() as s:
        assert await bot_login.find_pending(s, started["token"]) is None

    started = await _start(client)
    assert await _answer(started, KID_TG, None) == "rejected"
    r = await client.post("/api/auth/bot/poll", json={"token": started["token"]})
    assert r.status_code == 403


async def test_expired_and_unknown(client):
    await make_student()
    started = await _start(client)
    async with SessionLocal() as s:
        row = await s.scalar(select(LoginRequest))
        row.expires_at = utcnow() - timedelta(seconds=1)
        await s.commit()
    r = await client.post("/api/auth/bot/poll", json={"token": started["token"]})
    assert r.status_code == 410
    async with SessionLocal() as s:
        user = await get_by_telegram(s, KID_TG)
        assert await bot_login.answer(s, row.id, user, started["code"]) == "expired"

    r = await client.post("/api/auth/bot/poll", json={"token": "x" * 32})
    assert r.status_code == 410


async def test_blocked_user_cannot_finish_login(client):
    await make_student()
    started = await _start(client)
    assert await _answer(started, KID_TG, started["code"]) == "confirmed"
    async with SessionLocal() as s:
        await block_user(s, KID_TG, "спам")
        await s.commit()
    r = await client.post("/api/auth/bot/poll", json={"token": started["token"]})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "blocked"


# ---------- Вход для ментора ----------

MENTOR_TG = 5151


async def test_mentor_widget_login_assigns_role(client):
    r = await client.post(
        "/api/auth/telegram", json={"widget": widget_payload(MENTOR_TG), "as_role": "teacher"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["me"]["role"] == "teacher"
    # повторный вход ментора — тоже ок
    r = await client.post(
        "/api/auth/telegram", json={"widget": widget_payload(MENTOR_TG), "as_role": "teacher"}
    )
    assert r.status_code == 200 and r.json()["me"]["role"] == "teacher"


async def test_mentor_widget_login_rejects_student_and_parent(client):
    await make_student()  # ученик KID_TG и родитель KID_TG + 1
    for tg_id in (KID_TG, KID_TG + 1):
        r = await client.post(
            "/api/auth/telegram", json={"widget": widget_payload(tg_id), "as_role": "teacher"}
        )
        assert r.status_code == 403 and r.json()["detail"]["code"] == "not_mentor"
    async with SessionLocal() as s:
        assert (await get_by_telegram(s, KID_TG)).role == "student"  # роль не тронута


async def test_mentor_bot_login_flow(client):
    r = await client.post("/api/auth/bot/start", json={"as_role": "teacher"})
    started = r.json()
    async with SessionLocal() as s:
        user = await upsert_telegram_user(s, MENTOR_TG, "mentor", "Ментор")
        await s.commit()
    assert await _answer(started, MENTOR_TG, started["code"]) == "confirmed"
    r = await client.post("/api/auth/bot/poll", json={"token": started["token"]})
    assert r.status_code == 200, r.text
    assert r.json()["me"]["id"] == user.id and r.json()["me"]["role"] == "teacher"


async def test_mentor_bot_login_rejects_student(client):
    await make_student()
    started = await client.post("/api/auth/bot/start", json={"as_role": "teacher"})
    started = started.json()
    assert await _answer(started, KID_TG, started["code"]) == "not_mentor"
    r = await client.post("/api/auth/bot/poll", json={"token": started["token"]})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "not_mentor"
    async with SessionLocal() as s:
        assert (await get_by_telegram(s, KID_TG)).role == "student"


async def test_regular_bot_login_does_not_assign_role(client):
    started = await _start(client)
    async with SessionLocal() as s:
        await upsert_telegram_user(s, MENTOR_TG, "x", "X")
        await s.commit()
    assert await _answer(started, MENTOR_TG, started["code"]) == "confirmed"
    r = await client.post("/api/auth/bot/poll", json={"token": started["token"]})
    assert r.json()["me"]["role"] is None


# ---------- Обычный вход через Telegram — это вход ученика ----------


async def _widget_login(client, tg_id: int, as_role: str | None) -> dict:
    r = await client.post("/api/auth/telegram", json={"widget": widget_payload(tg_id), "as_role": as_role})
    assert r.status_code == 200, r.text
    return r.json()["me"]


async def test_student_login_makes_new_user_student(client):
    me = await _widget_login(client, MENTOR_TG, "student")
    assert me["role"] == "student" and me["student"] is not None


async def test_student_login_turns_childless_parent_into_student(client):
    async with SessionLocal() as s:
        user = await upsert_telegram_user(s, MENTOR_TG, "kid", "Кид")
        user.role = "parent"  # ребёнок по ошибке выбрал «Родитель» в боте
        await s.commit()
    assert (await _widget_login(client, MENTOR_TG, "student"))["role"] == "student"


async def test_student_login_keeps_real_parent_and_mentor(client):
    await make_student()  # родитель KID_TG + 1 с привязанным ребёнком
    assert (await _widget_login(client, KID_TG + 1, "student"))["role"] == "parent"
    await _widget_login(client, MENTOR_TG, "teacher")
    assert (await _widget_login(client, MENTOR_TG, "student"))["role"] == "teacher"


async def test_student_bot_login_makes_student(client):
    started = (await client.post("/api/auth/bot/start", json={"as_role": "student"})).json()
    async with SessionLocal() as s:
        await upsert_telegram_user(s, MENTOR_TG, "kid", "Кид")
        await s.commit()
    assert await _answer(started, MENTOR_TG, started["code"]) == "confirmed"
    r = await client.post("/api/auth/bot/poll", json={"token": started["token"]})
    assert r.json()["me"]["role"] == "student"


def test_parent_consent_off_only_in_demo():
    settings = get_settings()
    assert settings.model_copy(update={"require_parent_consent": None, "gemini_fake": False}).parent_consent_required
    assert not settings.model_copy(update={"require_parent_consent": None, "gemini_fake": True}).parent_consent_required
    assert not settings.model_copy(
        update={"require_parent_consent": None, "gemini_fake": False, "demo_mode": True}
    ).parent_consent_required
    assert settings.model_copy(update={"require_parent_consent": True, "gemini_fake": True}).parent_consent_required


async def test_no_parent_consent_needed_in_demo(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "require_parent_consent", None)  # демо: GEMINI_FAKE=1
    await make_student(consent=False)
    me = await _widget_login(client, KID_TG, "student")
    assert me["student"]["consent_confirmed"] is True  # сайт не показывает «ждём согласия»
    headers = await login(client)
    r = await client.post("/api/explain", data={"title": "дроби"}, headers=headers)
    assert r.status_code == 200, r.text


def test_choices_contain_code_once():
    request = LoginRequest(match_code=42)
    for _ in range(50):
        choices = bot_login.choices_for(request)
        assert len(choices) == 3 and len(set(choices)) == 3 and 42 in choices
