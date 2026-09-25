"""Модуль 4: вход по номеру телефона с SMS-кодом и семейный аккаунт."""
from __future__ import annotations

import re
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.timeutil import utcnow
from app.db.models import SmsCode
from app.db.session import SessionLocal
from app.main import app
from app.repositories.users import upsert_telegram_user
from app.services.accounts import choose_role
from app.services.sms import MemorySender, SmsError, normalize_phone
from test_api import login, make_student


@pytest.fixture
def sms_box():
    box = MemorySender()
    app.state.sms = box
    yield box
    app.state.sms = None


def last_code(box: MemorySender) -> str:
    return re.search(r"\b(\d{6})\b", box.sent[-1][1]).group(1)


async def sms_login(client, box, phone: str, role: str | None = "parent") -> dict:
    r = await client.post("/api/v1/auth/sms/request", json={"phone": phone, "lang": "ru"})
    assert r.status_code == 200, r.text
    r = await client.post("/api/v1/auth/sms/verify", json={"phone": phone, "code": last_code(box)})
    assert r.status_code == 200, r.text
    headers = {"Authorization": f"Bearer {r.json()['token']}"}
    if role:
        r = await client.post("/api/v1/me/role", json={"role": role, "name": "Мама"}, headers=headers)
        assert r.status_code == 200 and r.json()["role"] == role
    return headers


def test_normalize_phone():
    for raw in ("+998 90 123-45-67", "998901234567", "90 123 45 67", "(90) 1234567"):
        assert normalize_phone(raw) == "+998901234567"
    for bad in ("12345", "+7 900 123 45 67", ""):
        with pytest.raises(SmsError):
            normalize_phone(bad)


async def test_sms_login_flow(client, sms_box):
    r = await client.post("/api/v1/auth/sms/request", json={"phone": "90 123 45 67"})
    assert r.json() == {"phone": "+998901234567", "ttl": 300, "resend_after": 60}
    assert sms_box.sent[-1][0] == "+998901234567" and "EDU ProgressUZ" in sms_box.sent[-1][1]
    code = last_code(sms_box)
    async with SessionLocal() as s:  # в БД — не сам код, а HMAC
        assert code not in (await s.scalar(select(SmsCode))).code_hash

    # Повторная отправка — не раньше чем через минуту
    r = await client.post("/api/v1/auth/sms/request", json={"phone": "+998901234567"})
    assert r.status_code == 429 and r.json()["detail"]["code"] == "sms_too_soon"

    wrong = "000000" if code != "000000" else "111111"
    r = await client.post("/api/v1/auth/sms/verify", json={"phone": "+998901234567", "code": wrong})
    assert r.status_code == 401 and r.json()["detail"] == {"code": "sms_wrong", "attempts_left": 4}

    r = await client.post("/api/v1/auth/sms/verify", json={"phone": "901234567", "code": code})
    assert r.status_code == 200 and r.json()["me"]["role"] is None
    headers = {"Authorization": f"Bearer {r.json()['token']}"}
    # Код одноразовый
    r2 = await client.post("/api/v1/auth/sms/verify", json={"phone": "901234567", "code": code})
    assert r2.status_code == 410

    # Первый вход: роль ученика с классом
    r = await client.post("/api/v1/me/role", json={"role": "student", "name": "Азиз", "grade": 5}, headers=headers)
    assert r.json()["role"] == "student" and r.json()["name"] == "Азиз" and r.json()["student"]["grade"] == 5
    assert (await client.post("/api/v1/me/role", json={"role": "parent"}, headers=headers)).status_code == 409

    # Тот же номер — тот же пользователь
    async with SessionLocal() as s:
        (await s.scalar(select(SmsCode).order_by(SmsCode.id.desc()))).created_at -= timedelta(minutes=2)
        await s.commit()
    again = await sms_login(client, sms_box, "+998901234567", role=None)
    assert (await client.get("/api/me", headers=again)).json()["id"] == r.json()["id"]


async def test_sms_limits(client, sms_box):
    phone = "+998931112233"
    await client.post("/api/v1/auth/sms/request", json={"phone": phone})
    # 5 неверных попыток — код заблокирован даже для правильного значения
    for _ in range(4):
        await client.post("/api/v1/auth/sms/verify", json={"phone": phone, "code": "999999" if last_code(sms_box) != "999999" else "888888"})
    r = await client.post("/api/v1/auth/sms/verify", json={"phone": phone, "code": "999999" if last_code(sms_box) != "999999" else "888888"})
    assert r.status_code == 429 and r.json()["detail"]["code"] == "sms_locked"
    r = await client.post("/api/v1/auth/sms/verify", json={"phone": phone, "code": last_code(sms_box)})
    assert r.status_code == 429

    # Истёкший код
    async with SessionLocal() as s:
        for row in await s.scalars(select(SmsCode)):
            row.created_at -= timedelta(minutes=10)
            row.expires_at = utcnow() - timedelta(seconds=1)
        await s.commit()
    await client.post("/api/v1/auth/sms/request", json={"phone": "+998941112233"})
    async with SessionLocal() as s:
        row = await s.scalar(select(SmsCode).where(SmsCode.phone == "+998941112233"))
        row.expires_at = utcnow() - timedelta(seconds=1)
        await s.commit()
    r = await client.post("/api/v1/auth/sms/verify", json={"phone": "+998941112233", "code": last_code(sms_box)})
    assert r.status_code == 410 and r.json()["detail"]["code"] == "sms_expired"

    # Не больше 5 SMS в час на номер
    async with SessionLocal() as s:
        for i in range(5):
            s.add(SmsCode(phone="+998951112233", code_hash="x", attempts=0,
                          created_at=utcnow() - timedelta(minutes=5 + i), expires_at=utcnow()))
        await s.commit()
    r = await client.post("/api/v1/auth/sms/request", json={"phone": "+998951112233"})
    assert r.status_code == 429 and r.json()["detail"]["code"] == "sms_limit"


async def test_family_invite_join_and_links(client, sms_box):
    kid_id = await make_student()  # ученик из бота
    kid = await login(client)
    r = await client.post("/api/v1/family/invites", headers=kid)
    assert r.status_code == 200
    invite = r.json()
    assert re.fullmatch(r"\d{6}", invite["code"])
    assert "<svg" in invite["qr_svg"] and "<path" in invite["qr_svg"]
    assert invite["join_url"].endswith(f"/family/join?code={invite['code']}")

    # Родитель без подтверждённого номера (вошёл через Telegram) — сначала SMS
    async with SessionLocal() as s:
        tg_parent = await upsert_telegram_user(s, 8800, None, "Папа")
        await choose_role(s, tg_parent, "parent")
        await s.commit()
    r = await client.post("/api/v1/family/join", json={"code": invite["code"]}, headers=await login(client, 8800))
    assert r.status_code == 403 and r.json()["detail"]["code"] == "phone_required"

    mom = await sms_login(client, sms_box, "+998901000001")
    r = await client.post("/api/v1/family/join", json={"code": invite["code"]}, headers=mom)
    assert r.status_code == 200
    family = (await client.get("/api/v1/family", headers=mom)).json()
    assert sorted(m["role"] for m in family["members"]) == ["parent", "student"]
    assert family["members"][1]["phone"].endswith("00 01") and "*" in family["members"][1]["phone"]
    # Семья даёт доступ: мама видит ребёнка в журнале
    journal = (await client.get("/api/journal", headers=mom)).json()
    assert [s["id"] for s in journal["students"]] == [kid_id]

    # Код одноразовый; повторное вступление — понятная ошибка
    r = await client.post("/api/v1/family/join", json={"code": invite["code"]}, headers=mom)
    assert r.status_code == 404 and r.json()["detail"]["code"] == "invite_invalid"

    # Второй взрослый по новому приглашению от мамы — тоже видит ребёнка (многие ко многим)
    code2 = (await client.post("/api/v1/family/invites", headers=mom)).json()["code"]
    dad = await sms_login(client, sms_box, "+998901000002")
    assert (await client.post("/api/v1/family/join", json={"code": code2}, headers=dad)).status_code == 200
    assert [s["id"] for s in (await client.get("/api/journal", headers=dad)).json()["students"]] == [kid_id]

    # Лимит: до 4 взрослых
    for n in (3, 4, 5):
        code = (await client.post("/api/v1/family/invites", headers=mom)).json()["code"]
        adult = await sms_login(client, sms_box, f"+99890100000{n}")
        r = await client.post("/api/v1/family/join", json={"code": code}, headers=adult)
        assert r.status_code == (200 if n <= 4 else 409)
    assert r.json()["detail"]["code"] == "family_full_adults"

    # Учитель — не член семьи
    async with SessionLocal() as s:
        teacher = await upsert_telegram_user(s, 8900, None, "Учитель")
        await choose_role(s, teacher, "teacher")
        await s.commit()
    r = await client.post("/api/v1/family/invites", headers=await login(client, 8900))
    assert r.status_code == 403 and r.json()["detail"]["code"] == "family_role_required"
