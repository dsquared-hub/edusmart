"""Кабинеты родителя и учителя: сводка только по своим ученикам."""
from __future__ import annotations

from app.db.session import SessionLocal
from app.repositories.students import link_teacher
from test_api import KID_TG, login, make_student
from test_journal import MOM_TG, TEACHER_TG, _complete_topic, _user


async def test_parent_cabinet_shows_only_own_children(client):
    kid_id = await make_student()
    await _complete_topic(client, await login(client), "дроби", first_wrong=True)
    other_id = await make_student(tg_id=5000)  # чужой ребёнок (родитель 5001)
    await _complete_topic(client, await login(client, 5000), "проценты")

    r = await client.get("/api/cabinet", headers=await login(client, MOM_TG))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["role"] == "parent"
    [child] = body["children"]
    assert child["id"] == kid_id and child["name"] == "Аня"
    assert child["topics_week"] == 1 and child["accuracy"] == 75
    assert child["evening"] is None  # вечерний тест сегодня ещё не начат

    other = (await client.get("/api/cabinet", headers=await login(client, 5001))).json()
    assert [c["id"] for c in other["children"]] == [other_id]


async def test_teacher_cabinet_counts_linked_students_only(client):
    kid_id = await make_student()
    await _complete_topic(client, await login(client), "дроби", first_wrong=True)
    await make_student(tg_id=5000)
    await _complete_topic(client, await login(client, 5000), "проценты")
    teacher_id = await _user(TEACHER_TG, "teacher", "Учитель")
    headers = await login(client, TEACHER_TG)

    empty = (await client.get("/api/cabinet", headers=headers)).json()["class"]
    assert empty["students"] == 0 and empty["accuracy"] is None

    async with SessionLocal() as s:
        await link_teacher(s, teacher_id, kid_id)
        await s.commit()
    summary = (await client.get("/api/cabinet", headers=headers)).json()["class"]
    assert summary["students"] == 1 and summary["topics_week"] == 1
    assert summary["accuracy"] == 75 and summary["active_today"] == 1
    assert summary["weak"] == [{"title": "дроби", "mistakes": 1}]
    assert summary["checks_to_review"] == 0


async def test_cabinet_forbidden_for_students_and_guests(client):
    await make_student()
    assert (await client.get("/api/cabinet", headers=await login(client, KID_TG))).status_code == 403
    assert (await client.get("/api/cabinet")).status_code == 401
