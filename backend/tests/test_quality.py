"""Качество и безопасность: проверка ответов модели, очки за попытки, лимиты,
жалобы, согласие по версии политики, удаление данных, отзыв токенов, лимит по IP."""
from __future__ import annotations

import httpx
import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.models import ConsentRecord, ContentReport, Event, Topic, User
from app.db.session import SessionLocal
from app.main import app, create_app
from app.repositories.students import get_student
from app.repositories.users import upsert_telegram_user
from app.services.accounts import (
    AccountError,
    confirm_consent_for_children,
    create_child_access,
    delete_student_data,
    regenerate_code,
)
from app.services.explain import ExplainService, points_for_attempt
from app.services.gemini_stub import StubLessonService
from test_api import CORRECT, KID_TG, login, make_student


def service() -> ExplainService:
    return app.state.explain


# ---------- Проверка ответов модели ----------

def test_option_explanations_are_optional():
    from app.services.gemini import validate_steps

    step = {"title": "t", "text": "x", "example": "e", "check_question": "q",
            "options": ["a", "b"], "correct": 0}
    good = validate_steps({"steps": [{**step, "explanations": [" да ", "нет"]}]}, 1, 1)
    assert good[0]["explanations"] == ["да", "нет"]
    # Не на каждый вариант или пустые — урок принимаем, пояснений просто нет
    for bad in (["да"], ["да", ""], "да", None):
        steps = validate_steps({"steps": [{**step, "explanations": bad}]}, 1, 1)
        assert steps[0]["explanations"] is None


async def test_wrong_answer_from_model_is_regenerated(client):
    await make_student()
    headers = await login(client)
    stub = service().lesson
    stub.wrong_answers = 1  # первая генерация с ошибкой в «correct»
    r = await client.post("/api/explain", data={"title": "дроби"}, headers=headers)
    assert r.status_code == 200
    assert stub.verify_calls == 2  # проверили оба варианта
    # ученик получил исправленный урок: верный ответ шага 1 — «3/8»
    r = await client.post(f"/api/explain/{r.json()['id']}/answer", json={"step": 0, "option": 0}, headers=headers)
    assert r.json()["correct"]


async def test_unverifiable_explanation_is_not_shown(client):
    await make_student()
    headers = await login(client)
    service().lesson.wrong_answers = 2  # обе попытки с ошибкой
    r = await client.post("/api/explain", data={"title": "дроби"}, headers=headers)
    assert r.status_code == 502 and r.json()["detail"]["code"] == "generation_failed"
    progress = (await client.get("/api/progress", headers=headers)).json()
    assert progress["explanations_left_today"] == 20  # попытку вернули
    async with SessionLocal() as s:
        assert await s.scalar(select(func.count(Topic.id))) == 0


class ArithmeticModel(StubLessonService):
    """Модель, которая ошиблась в умножении, а проверяющий этого не заметил."""

    calls = 0

    async def explain_topic(self, title, **kwargs):
        self.calls += 1
        steps = await super().explain_topic(title, **kwargs)
        steps[0]["check_question"] = "Сколько будет 12 × 3?"
        steps[0]["options"] = ["33", "36", "39"]
        steps[0]["correct"] = 0 if self.calls == 1 else 1
        return steps

    async def verify_answers(self, items):
        return [{"ok": True, "correct": i["correct"], "issue": ""} for i in items]


async def test_arithmetic_is_checked_without_ai(db):
    model = ArithmeticModel()
    explain = ExplainService(model, get_settings())
    kid_id = await make_student()
    async with SessionLocal() as s:
        topic = await explain.start(s, kid_id, "умножение")
    assert model.calls == 2 and topic.steps[0]["correct"] == 1


async def test_verifier_outage_does_not_block_child(db):
    class Down(StubLessonService):
        async def verify_answers(self, items):
            raise RuntimeError("503")

    kid_id = await make_student()
    async with SessionLocal() as s:
        topic = await ExplainService(Down(), get_settings()).start(s, kid_id, "дроби")
    assert topic.total_steps == 4


async def test_practice_is_verified(client):
    await make_student()
    headers = await login(client)
    tid = (await client.post("/api/explain", data={"title": "дроби"}, headers=headers)).json()["id"]
    for step, option in enumerate(CORRECT):
        await client.post(f"/api/explain/{tid}/answer", json={"step": step, "option": option}, headers=headers)
    service().lesson.verifier_disagrees = True
    r = await client.post(f"/api/explain/{tid}/practice", headers=headers)
    assert r.status_code == 502


# ---------- Очки только за 1–2 попытку ----------

def test_points_for_attempt():
    s = get_settings()
    assert [points_for_attempt(n, s) for n in range(4)] == [10, 5, 0, 0]


async def test_guessing_gives_no_points(client):
    await make_student()
    headers = await login(client)
    tid = (await client.post("/api/explain", data={"title": "дроби"}, headers=headers)).json()["id"]
    for option in (1, 2):  # перебор: два неверных
        await client.post(f"/api/explain/{tid}/answer", json={"step": 0, "option": option}, headers=headers)
    r = (await client.post(f"/api/explain/{tid}/answer", json={"step": 0, "option": 0}, headers=headers)).json()
    assert r["correct"] and r["points_awarded"] == 0 and r["attempts"] == 3


# ---------- Лимиты упрощений ----------

async def test_simplify_limit_per_step(client):
    await make_student()
    headers = await login(client)
    tid = (await client.post("/api/explain", data={"title": "дроби"}, headers=headers)).json()["id"]
    for _ in range(3):
        assert (await client.post(f"/api/explain/{tid}/simplify", headers=headers)).status_code == 200
    r = await client.post(f"/api/explain/{tid}/simplify", headers=headers)
    assert r.status_code == 429 and r.json()["detail"]["code"] == "simplify_limit"
    topic = (await client.get(f"/api/explain/{tid}", headers=headers)).json()
    assert topic["steps"][0]["simplify_left"] == 0 and topic["steps"][1]["simplify_left"] == 3


async def test_daily_simplify_limit(client):
    await make_student()
    headers = await login(client)
    service().settings = service().settings.model_copy(update={"daily_simplify_limit": 2})
    tid = (await client.post("/api/explain", data={"title": "дроби"}, headers=headers)).json()["id"]
    codes = [(await client.post(f"/api/explain/{tid}/simplify", headers=headers)).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


# ---------- «⚠️ Здесь ошибка» ----------

async def test_report_mistake(client):
    await make_student()
    headers = await login(client)
    tid = (await client.post("/api/explain", data={"title": "дроби"}, headers=headers)).json()["id"]
    r = await client.post(f"/api/explain/{tid}/report", json={"step": 1, "comment": "ответ неверный"}, headers=headers)
    assert r.json() == {"ok": True, "already_reported": False}
    r = await client.post(f"/api/explain/{tid}/report", json={"step": 1}, headers=headers)
    assert r.json()["already_reported"]
    assert (await client.post(f"/api/explain/{tid}/report", json={"step": 9}, headers=headers)).status_code == 400
    async with SessionLocal() as s:
        report = await s.scalar(select(ContentReport))
        assert (report.step_index, report.comment, report.status) == (1, "ответ неверный", "open")
        assert await s.scalar(select(Event.type)) == "content_report"


# ---------- Согласие по версии политики ----------

async def test_consent_must_match_policy_version(client):
    kid_id = await make_student()
    async with SessionLocal() as s:
        (await get_student(s, kid_id)).consent_version = "legacy"  # согласие на старую политику
        await s.commit()
    headers = await login(client)
    r = await client.post("/api/explain", data={"title": "дроби"}, headers=headers)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "consent_required"
    assert (await client.get("/api/me", headers=headers)).json()["student"]["consent_confirmed"] is False

    async with SessionLocal() as s:
        mom = await upsert_telegram_user(s, KID_TG + 1)
        assert await confirm_consent_for_children(s, mom) == 1
    async with SessionLocal() as s:
        record = await s.scalar(select(ConsentRecord))
        assert record.policy_version == get_settings().policy_version
        assert record.parent_telegram_id == KID_TG + 1 and record.action == "granted"
    assert (await client.post("/api/explain", data={"title": "дроби"}, headers=headers)).status_code == 200


async def test_parent_created_login_logs_consent(db):
    async with SessionLocal() as s:
        dad = await upsert_telegram_user(s, 42, "d", "Папа")
        dad.role = "parent"
        issued = await create_child_access(s, dad, "Тимур")
    async with SessionLocal() as s:
        record = await s.scalar(select(ConsentRecord))
        assert record.student_user_id == issued.user.id and record.channel == "bot"


# ---------- Удаление данных ребёнка ----------

async def test_parent_deletes_child_data(client):
    kid_id = await make_student()
    headers = await login(client)
    tid = (await client.post("/api/explain", data={"title": "дроби"}, headers=headers)).json()["id"]
    await client.post(f"/api/explain/{tid}/report", json={"step": 0}, headers=headers)

    async with SessionLocal() as s:
        stranger = await upsert_telegram_user(s, 777_777)
        with pytest.raises(AccountError):
            await delete_student_data(s, stranger, kid_id)
    async with SessionLocal() as s:
        mom = await upsert_telegram_user(s, KID_TG + 1)
        assert await delete_student_data(s, mom, kid_id) == "Аня"
    async with SessionLocal() as s:
        assert await s.get(User, kid_id) is None
        assert await s.scalar(select(func.count(Topic.id))) == 0
        assert await s.scalar(select(func.count(ContentReport.id))) == 0
        actions = list(await s.scalars(select(ConsentRecord.action)))
        assert actions == ["deleted"]  # след в журнале остался
    assert (await client.get("/api/me", headers=headers)).status_code == 401


# ---------- Отзыв токенов ----------

async def test_logout_revokes_all_tokens(client):
    await make_student()
    phone = await login(client)
    laptop = await login(client)
    assert (await client.post("/api/auth/logout", headers=phone)).json() == {"ok": True}
    assert (await client.get("/api/me", headers=phone)).status_code == 401
    assert (await client.get("/api/me", headers=laptop)).status_code == 401
    assert (await client.get("/api/me", headers=await login(client))).status_code == 200


async def test_new_code_revokes_child_sessions(client):
    async with SessionLocal() as s:
        dad = await upsert_telegram_user(s, 42, "d", "Папа")
        dad.role = "parent"
        issued = await create_child_access(s, dad, "Тимур")
    r = await client.post("/api/auth/code", json={"login": issued.login, "code": issued.code})
    headers = {"Authorization": f"Bearer {r.json()['token']}"}
    async with SessionLocal() as s:
        dad = await s.get(User, dad.id)
        await regenerate_code(s, dad, issued.user.id)
    assert (await client.get("/api/me", headers=headers)).status_code == 401


# ---------- Лимит частоты по IP и здоровье ----------

async def test_rate_limit_per_ip(db):
    limited = create_app(get_settings().model_copy(update={"rate_limit_auth": 3}))
    limited.state.explain = ExplainService(StubLessonService(), get_settings())
    transport = httpx.ASGITransport(app=limited)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        codes = [
            (await c.post("/api/auth/code", json={"login": "nobody", "code": "000000"})).status_code
            for _ in range(4)
        ]
        assert codes == [401, 401, 401, 429]
        r = await c.post("/api/auth/code", json={"login": "nobody", "code": "000000"})
        assert r.json()["detail"]["code"] == "rate_limited" and int(r.headers["Retry-After"]) > 0
        assert (await c.get("/api/config")).status_code == 200  # другие группы не задеты
        assert (await c.get("/api/health")).json() == {"ok": True, "db": True}
