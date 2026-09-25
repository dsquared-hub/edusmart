"""Журнал результатов: родитель и учитель видят закрытые темы своих учеников."""
from __future__ import annotations

from app.db.session import SessionLocal
from app.repositories.students import link_teacher
from app.repositories.users import upsert_telegram_user
from app.services.accounts import choose_role
from test_api import CORRECT, KID_TG, login, make_student

MOM_TG = KID_TG + 1  # родитель, которого создаёт make_student
TEACHER_TG = 3030


async def _complete_topic(client, headers, title: str, *, first_wrong: bool = False) -> int:
    tid = (await client.post("/api/explain", data={"title": title}, headers=headers)).json()["id"]
    if first_wrong:  # шаг 0 — сначала неверно, потом верно
        await client.post(f"/api/explain/{tid}/answer", json={"step": 0, "option": 2}, headers=headers)
    for step, option in enumerate(CORRECT):
        r = await client.post(
            f"/api/explain/{tid}/answer", json={"step": step, "option": option}, headers=headers
        )
        assert r.status_code == 200, r.text
    assert r.json()["completed"]
    return tid


async def _user(tg_id: int, role: str, name: str) -> int:
    async with SessionLocal() as s:
        user = await upsert_telegram_user(s, tg_id, None, name)
        await choose_role(s, user, role)
        await s.commit()
        return user.id


async def test_parent_sees_results_of_child(client):
    kid_id = await make_student()
    kid = await login(client)
    tid = await _complete_topic(client, kid, "дроби", first_wrong=True)
    # незакрытая тема в журнал не попадает
    await client.post("/api/explain", data={"title": "проценты"}, headers=kid)

    r = await client.get("/api/journal", headers=await login(client, MOM_TG))
    assert r.status_code == 200, r.text
    body = r.json()
    assert [s["id"] for s in body["students"]] == [kid_id]
    student = body["students"][0]
    assert student["name"] == "Аня" and student["topics_completed"] == 1
    assert student["topics_week"] == 1 and student["accuracy"] == 75  # 3 из 4 с первой попытки
    assert student["weak"] == [{"title": "дроби", "mistakes": 1}]

    assert body["has_more"] is False
    [entry] = body["entries"]
    assert entry["topic_id"] == tid and entry["student_name"] == "Аня"
    assert entry["questions"] == 4 and entry["first_try"] == 3 and entry["mistakes"] == 1
    assert entry["points"] == 35 and entry["source"] == "web"
    assert entry["completed_at"].endswith("+00:00")  # время с явной зоной UTC


async def test_teacher_sees_only_linked_students(client):
    kid_id = await make_student()
    await _complete_topic(client, await login(client), "дроби")
    other_id = await make_student(tg_id=5000)
    await _complete_topic(client, await login(client, 5000), "проценты")

    teacher_id = await _user(TEACHER_TG, "teacher", "Учитель")
    headers = await login(client, TEACHER_TG)
    assert (await client.get("/api/journal", headers=headers)).json() == {
        "students": [], "entries": [], "has_more": False
    }

    async with SessionLocal() as s:
        await link_teacher(s, teacher_id, kid_id)
        await s.commit()
    body = (await client.get("/api/journal", headers=headers)).json()
    assert [s["id"] for s in body["students"]] == [kid_id]
    assert [e["title"] for e in body["entries"]] == ["дроби"]
    assert body["students"][0]["accuracy"] == 100 and body["students"][0]["weak"] == []

    # Чужой ученик — 404, как будто его нет
    r = await client.get(f"/api/journal?student_id={other_id}", headers=headers)
    assert r.status_code == 404 and r.json()["detail"]["code"] == "student_not_found"


async def test_student_filter_and_pagination(client):
    await make_student()
    kid = await login(client)
    ids = [await _complete_topic(client, kid, f"тема {n}") for n in range(3)]
    parent = await login(client, MOM_TG)

    first = (await client.get("/api/journal?limit=2", headers=parent)).json()
    assert [e["topic_id"] for e in first["entries"]] == [ids[2], ids[1]]  # новые сверху
    assert first["has_more"] is True
    r = await client.get(f"/api/journal?limit=2&before={ids[1]}", headers=parent)
    rest = r.json()
    assert [e["topic_id"] for e in rest["entries"]] == [ids[0]] and rest["has_more"] is False

    kid_id = first["students"][0]["id"]
    r = await client.get(f"/api/journal?student_id={kid_id}", headers=parent)
    assert len(r.json()["entries"]) == 3
    assert (await client.get("/api/journal?limit=0", headers=parent)).status_code == 422


async def test_journal_only_for_parent_or_teacher(client):
    await make_student()
    r = await client.get("/api/journal", headers=await login(client))
    assert r.status_code == 403 and r.json()["detail"]["code"] == "not_parent_or_teacher"
    assert (await client.get("/api/journal")).status_code == 401
