"""Модуль 4: семейный аккаунт и номер телефона из бота."""
from __future__ import annotations

import re

import pytest

from app.db.session import SessionLocal
from app.repositories.users import upsert_telegram_user
from app.services.accounts import AccountError, choose_role, issue_own_access
from app.services.registration import normalize_phone
from test_api import login, make_student


async def adult_with_phone(client, tg_id: int, phone: str, role: str = "parent") -> dict:
    """Взрослый из бота, поделившийся номером кнопкой «Поделиться номером»."""
    async with SessionLocal() as s:
        user = await upsert_telegram_user(s, tg_id, None, "Мама")
        await choose_role(s, user, role)
        user.phone = phone
        await s.commit()
    return await login(client, tg_id)


async def test_adult_site_login_from_bot(client):
    """Бот выдаёт взрослому логин и код — с ними он входит на сайт как родитель / учитель."""
    for tg_id, role in ((8101, "parent"), (8102, "teacher")):
        async with SessionLocal() as s:
            user = await upsert_telegram_user(s, tg_id, None, "Малика")
            await choose_role(s, user, role)
            login_, code = await issue_own_access(s, user)
            _, new_code = await issue_own_access(s, user)
        assert re.fullmatch(r"malika\d{3}", login_)
        r = await client.post("/api/auth/code", json={"login": login_, "code": new_code})
        assert r.status_code == 200, r.text
        assert r.json()["me"]["role"] == role
        if new_code != code:  # старый код после выдачи нового не работает
            r = await client.post("/api/auth/code", json={"login": login_, "code": code})
            assert r.status_code == 401


async def test_site_access_not_for_students_or_unregistered():
    async with SessionLocal() as s:
        nobody = await upsert_telegram_user(s, 8103, None, "Кто-то")
        with pytest.raises(AccountError):
            await issue_own_access(s, nobody)
        await choose_role(s, nobody, "student")
        with pytest.raises(AccountError):
            await issue_own_access(s, nobody)


def test_normalize_phone():
    for raw in ("+998 90 123-45-67", "998901234567", "90 123 45 67", "(90) 1234567"):
        assert normalize_phone(raw) == "+998901234567"
    for bad in ("12345", "+7 900 123 45 67", ""):
        with pytest.raises(AccountError):
            normalize_phone(bad)


async def test_family_invite_join_and_links(client):
    kid_id = await make_student()  # ученик из бота
    kid = await login(client)
    r = await client.post("/api/v1/family/invites", headers=kid)
    assert r.status_code == 200
    invite = r.json()
    assert re.fullmatch(r"\d{6}", invite["code"])
    assert "<svg" in invite["qr_svg"] and "<path" in invite["qr_svg"]
    assert invite["join_url"].endswith(f"/family/join?code={invite['code']}")

    # Родитель, не поделившийся номером в боте, — сначала номер
    async with SessionLocal() as s:
        tg_parent = await upsert_telegram_user(s, 8800, None, "Папа")
        await choose_role(s, tg_parent, "parent")
        await s.commit()
    r = await client.post("/api/v1/family/join", json={"code": invite["code"]}, headers=await login(client, 8800))
    assert r.status_code == 403 and r.json()["detail"]["code"] == "phone_required"

    mom = await adult_with_phone(client, 8801, "+998901000001")
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
    dad = await adult_with_phone(client, 8802, "+998901000002")
    assert (await client.post("/api/v1/family/join", json={"code": code2}, headers=dad)).status_code == 200
    assert [s["id"] for s in (await client.get("/api/journal", headers=dad)).json()["students"]] == [kid_id]

    # Лимит: до 4 взрослых
    for n in (3, 4, 5):
        code = (await client.post("/api/v1/family/invites", headers=mom)).json()["code"]
        adult = await adult_with_phone(client, 8800 + n, f"+99890100000{n}")
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
