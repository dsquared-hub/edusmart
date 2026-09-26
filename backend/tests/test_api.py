"""API сайта: вход, профиль, «Не понял тему», общий прогресс с ботом."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Event
from app.db.session import SessionLocal
from app.main import app
from app.repositories.blocks import block_user
from app.repositories.students import get_student, link_parent
from app.repositories.users import upsert_telegram_user
from app.services.accounts import choose_role, create_child_access
from app.services.gemini import validate_steps

TOKEN = "123456:TEST-TOKEN"
CORRECT = [0, 1, 1, 2]
KID_TG = 777


def widget_payload(tg_id: int, **extra) -> dict:
    data = {"id": tg_id, "first_name": "Аня", "username": "anya",
            "auth_date": int(time.time()), **extra}
    check = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hashlib.sha256(TOKEN.encode()).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return data


def init_data(tg_id: int, auth_date: int | None = None) -> str:
    fields = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "AAH",
        "user": json.dumps({"id": tg_id, "first_name": "Аня"}, ensure_ascii=False),
    }
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


async def make_student(tg_id: int = KID_TG, consent: bool = True) -> int:
    """Ученик, как его создаёт бот (+ родитель с согласием)."""
    async with SessionLocal() as s:
        user = await upsert_telegram_user(s, tg_id, "anya", "Аня")
        await choose_role(s, user, "student")
        student = await get_student(s, user.id)
        student.consent_confirmed = consent
        student.consent_version = get_settings().policy_version if consent else None
        mom = await upsert_telegram_user(s, tg_id + 1, "mom", "Мама")
        mom.role = "parent"
        await link_parent(s, mom.id, user.id)
        await s.commit()
        return user.id


async def login(client, tg_id: int = KID_TG) -> dict:
    r = await client.post("/api/auth/telegram", json={"widget": widget_payload(tg_id)})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


# ---------- Вход ----------

async def test_widget_login_is_same_user_as_bot(client):
    user_id = await make_student()
    r = await client.post("/api/auth/telegram", json={"widget": widget_payload(KID_TG)})
    me = r.json()["me"]
    assert me["id"] == user_id and me["role"] == "student" and me["has_telegram"]


async def test_mini_app_init_data_login(client):
    user_id = await make_student()
    r = await client.post("/api/auth/telegram", json={"init_data": init_data(KID_TG)})
    assert r.status_code == 200 and r.json()["me"]["id"] == user_id


@pytest.mark.parametrize(
    "body",
    [
        {"widget": {**widget_payload(KID_TG), "first_name": "Хакер"}},  # подмена поля
        {"widget": widget_payload(KID_TG, auth_date=int(time.time()) - 3 * 86400)},  # устарело
        {"init_data": init_data(KID_TG).replace("query_id=AAH", "query_id=XXX")},
        {"init_data": init_data(KID_TG, auth_date=int(time.time()) - 3 * 86400)},
        {},
    ],
)
async def test_bad_telegram_signatures_rejected(client, body):
    r = await client.post("/api/auth/telegram", json=body)
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "bad_telegram_auth"


async def test_code_login_and_lockout(client):
    async with SessionLocal() as s:
        parent = await upsert_telegram_user(s, 999, "p", "Папа")
        parent.role = "parent"
        issued = await create_child_access(s, parent, "Тимур", grade=5)
    r = await client.post("/api/auth/code", json={"login": issued.login, "code": issued.code})
    assert r.status_code == 200
    me = r.json()["me"]
    assert me["role"] == "student" and not me["has_telegram"]
    assert me["student"]["consent_confirmed"]

    for _ in range(5):
        r = await client.post("/api/auth/code", json={"login": issued.login, "code": "000000"})
    r = await client.post("/api/auth/code", json={"login": issued.login, "code": issued.code})
    assert r.status_code == 429 and r.json()["detail"]["code"] == "login_locked"


async def test_requires_auth(client):
    assert (await client.get("/api/me")).status_code == 401
    r = await client.get("/api/me", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


# ---------- Профиль и настройки ----------

async def test_me_and_settings_saved_in_profile(client):
    await make_student()
    headers = await login(client)
    r = await client.patch(
        "/api/me/settings",
        json={"theme": "night", "high_contrast": True, "dyslexia_font": True},
        headers=headers,
    )
    assert r.json()["settings"] == {
        "theme": "night", "high_contrast": True, "dyslexia_font": True, "lang": "ru"
    }
    assert (await client.get("/api/me", headers=headers)).json()["settings"]["theme"] == "night"
    r = await client.patch("/api/me/settings", json={"theme": "ocean"}, headers=headers)
    assert r.status_code == 422


# ---------- «Не понял тему» ----------

async def test_full_explain_flow(client):
    user_id = await make_student()
    headers = await login(client)

    r = await client.post(
        "/api/explain", data={"title": "дроби", "subject": "math", "grade": "5"}, headers=headers
    )
    assert r.status_code == 200, r.text
    topic = r.json()
    tid = topic["id"]
    assert topic["total_steps"] == 4 and topic["current_step"] == 0
    assert topic["source"] == "web" and topic["subject"] == "math"
    assert "correct" not in topic["steps"][0]  # ответ не утекает на клиент
    assert topic["steps"][0]["visual"]["type"] == "fractions"

    # Неверно → «Объясни проще» → тот же вопрос
    r = await client.post(f"/api/explain/{tid}/answer", json={"step": 0, "option": 2}, headers=headers)
    assert r.json()["correct"] is False and r.json()["points_awarded"] == 0
    r = await client.post(f"/api/explain/{tid}/simplify", headers=headers)
    simpler = r.json()["simpler"]
    assert simpler["title"] and "check_question" not in simpler
    r = await client.get(f"/api/explain/{tid}", headers=headers)
    assert r.json()["steps"][0]["simpler"] == simpler  # сохранилось для продолжения

    # шаг 1 — со второй попытки: 5 очков, остальные с первой: по 10
    for step, (option, points) in enumerate(zip(CORRECT, [5, 10, 10, 10])):
        r = await client.post(
            f"/api/explain/{tid}/answer", json={"step": step, "option": option}, headers=headers
        )
        body = r.json()
        assert body["correct"] and body["points_awarded"] == points
    assert body["completed"] and body["total_points"] == 35
    assert body["topic"]["status"] == "completed"
    assert body["topic"]["steps"][3]["correct"] == 2  # после закрытия — можно показать

    # Родителю уйдёт уведомление через очередь событий
    async with SessionLocal() as s:
        event = await s.scalar(select(Event))
        assert event.type == "topic_completed"
        assert event.payload["student_user_id"] == user_id and event.payload["source"] == "web"

    r = await client.post(f"/api/explain/{tid}/practice", headers=headers)
    assert len(r.json()["tasks"]) == 3

    progress = (await client.get("/api/progress", headers=headers)).json()
    assert progress["points"] == 35 and progress["topics_completed"] == 1
    assert progress["explanations_left_today"] == 19
    assert progress["recent"][0]["id"] == tid


async def test_stale_step_returns_current_topic(client):
    await make_student()
    headers = await login(client)
    tid = (await client.post("/api/explain", data={"title": "дроби"}, headers=headers)).json()["id"]
    await client.post(f"/api/explain/{tid}/answer", json={"step": 0, "option": 0}, headers=headers)
    r = await client.post(f"/api/explain/{tid}/answer", json={"step": 0, "option": 0}, headers=headers)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "stale_step"
    assert r.json()["detail"]["topic"]["current_step"] == 1


async def test_cannot_open_foreign_topic(client):
    await make_student()
    headers = await login(client)
    tid = (await client.post("/api/explain", data={"title": "дроби"}, headers=headers)).json()["id"]
    await make_student(tg_id=5000)
    other = await login(client, 5000)
    assert (await client.get(f"/api/explain/{tid}", headers=other)).status_code == 404


async def test_limit_consent_and_errors(client):
    await make_student(consent=False)
    headers = await login(client)
    r = await client.post("/api/explain", data={"title": "дроби"}, headers=headers)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "consent_required"

    await make_student(tg_id=6000)
    headers = await login(client, 6000)
    app.state.explain.settings = app.state.explain.settings.model_copy(
        update={"daily_explain_limit": 2}
    )
    app.state.explain.lesson.fail_next = True
    r = await client.post("/api/explain", data={"title": "дроби"}, headers=headers)
    assert r.status_code == 502  # ошибка модели — попытка возвращается
    for _ in range(2):
        assert (await client.post("/api/explain", data={"title": "x"}, headers=headers)).status_code == 200
    r = await client.post("/api/explain", data={"title": "x"}, headers=headers)
    assert r.status_code == 429 and r.json()["detail"]["code"] == "limit_reached"

    r = await client.post("/api/explain", data={"title": ""}, headers=headers)
    assert r.status_code in (422, 429)


async def test_photo_validation(client):
    await make_student()
    headers = await login(client)
    r = await client.post(
        "/api/explain",
        files={"photo": ("task.gif", b"GIF89a", "image/gif")},
        headers=headers,
    )
    assert r.status_code == 415
    big = b"\xff\xd8" + b"0" * (5 * 1024 * 1024 + 10)
    r = await client.post(
        "/api/explain", files={"photo": ("task.jpg", big, "image/jpeg")}, headers=headers
    )
    assert r.status_code == 413
    r = await client.post(
        "/api/explain", files={"photo": ("task.jpg", b"\xff\xd8\xff", "image/jpeg")}, headers=headers
    )
    assert r.status_code == 200 and r.json()["title"] == "Фото задания"


async def test_parent_cannot_explain(client):
    async with SessionLocal() as s:
        user = await upsert_telegram_user(s, 4242, "p", "Папа")
        await choose_role(s, user, "parent")
    headers = await login(client, 4242)
    r = await client.post("/api/explain", data={"title": "дроби"}, headers=headers)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "not_student"
    assert (await client.get("/api/progress", headers=headers)).status_code == 403


async def test_public_config(client):
    r = await client.get("/api/config")
    assert r.json()["bot_username"] == "edu_test_bot"


# ---------- Перенесено из обновлённого старого бота ----------

async def test_blocked_user_cannot_use_site(client):
    await make_student()
    headers = await login(client)  # сессия открыта до блокировки
    async with SessionLocal() as s:
        await block_user(s, KID_TG, "спам")
        await s.commit()
    r = await client.get("/api/me", headers=headers)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "blocked"
    r = await client.post("/api/auth/telegram", json={"widget": widget_payload(KID_TG)})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "blocked"


async def test_topic_too_long(client):
    await make_student()
    headers = await login(client)
    r = await client.post("/api/explain", data={"title": "а" * 501}, headers=headers)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "topic_too_long"
    progress = (await client.get("/api/progress", headers=headers)).json()
    assert progress["explanations_left_today"] == 20  # попытка не списана


def test_gemini_single_step_without_wrapper():
    step = {"title": "Проще", "text": "Текст", "example": "Пример",
            "check_question": "Вопрос?", "options": ["а", "б"], "correct": 1}
    assert validate_steps(step, 1, 1)[0]["correct"] == 1
    assert validate_steps(step, 3, 5) is None  # объяснению нужно 3–5 шагов
