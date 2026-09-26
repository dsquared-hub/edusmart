"""Вход через Telegram (виджет / Mini App): роль ментора и ученика, согласие в демо."""
from __future__ import annotations

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.users import get_by_telegram, upsert_telegram_user
from test_api import KID_TG, login, make_student, widget_payload

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
