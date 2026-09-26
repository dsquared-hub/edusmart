"""Квесты Paper-to-Digital: задача по пройденной теме, фото из тетради, EduCoin ×2 — один раз,
только если второй запрос подтвердил верное решение."""
from __future__ import annotations

import hashlib

from app.db.models import Student
from app.db.session import SessionLocal
from app.main import app
from app.services import paper_quests
from app.services.vision import StubWorkChecker
from test_api import CORRECT, KID_TG, login, make_student


def _photo(full: bool, confidence: int) -> bytes:
    """Байты, на которые заглушка ответит нужным баллом и уверенностью."""
    for i in range(10_000):
        data = b"\xff\xd8\xff photo " + str(i).encode()
        n = int(hashlib.sha256(data).hexdigest(), 16)
        if (n % 2 == 0) == full and (95, 80, 55)[n % 3] == confidence:
            return data
    raise AssertionError("не нашлось")


async def _completed_topic(client, headers) -> int:
    tid = (await client.post("/api/explain", data={"title": "дроби"}, headers=headers)).json()["id"]
    for step, option in enumerate(CORRECT):
        await client.post(f"/api/explain/{tid}/answer", json={"step": step, "option": option}, headers=headers)
    return tid


async def _send(client, headers, quest_id: int, data: bytes):
    return await client.post(
        f"/api/quests/{quest_id}/photo", files={"photo": ("page.jpg", data, "image/jpeg")}, headers=headers
    )


async def test_paper_quest_flow_and_double_coins(client):
    app.state.work_checker = checker = StubWorkChecker()
    kid_id = await make_student()
    headers = await login(client)
    topic_id = await _completed_topic(client, headers)

    quest = (await client.post("/api/quests", json={"topic_id": topic_id}, headers=headers)).json()
    assert quest["task"] and quest["answer"] is None  # ключ не показываем заранее
    assert quest["reward"] == paper_quests.DIGITAL_COINS * 2 and quest["attempts_left"] == 3
    # повторный запрос по той же теме — тот же открытый квест
    again = (await client.post("/api/quests", json={"topic_id": topic_id}, headers=headers)).json()
    assert again["id"] == quest["id"]

    wrong = (await _send(client, headers, quest["id"], _photo(full=False, confidence=95))).json()
    assert not wrong["passed"] and wrong["quest"]["attempts_left"] == 2 and wrong["marks"]
    blurry = (await _send(client, headers, quest["id"], _photo(full=True, confidence=55))).json()
    assert not blurry["passed"] and blurry["blurry"]  # неразборчиво — коины не даём

    calls = checker.calls
    ok = (await _send(client, headers, quest["id"], _photo(full=True, confidence=95))).json()
    assert ok["passed"] and ok["awarded"] and ok["total_coins"] == 6
    assert checker.calls - calls == 2  # второй независимый запрос подтвердил
    assert ok["quest"]["answer"]  # после прохождения ключ виден
    r = await _send(client, headers, quest["id"], _photo(full=True, confidence=95))
    assert r.status_code == 409  # коины — один раз

    async with SessionLocal() as s:
        assert (await s.get(Student, kid_id)).coins == 6


async def test_second_check_must_agree(client, monkeypatch):
    checker = StubWorkChecker()
    app.state.work_checker = checker
    await make_student()
    headers = await login(client)
    quest = (await client.post("/api/quests", json={"topic_id": await _completed_topic(client, headers)}, headers=headers)).json()

    original = checker.check_work
    answers = iter([True, False])  # первый запрос — «верно», второй — нет

    async def flaky(file, mime, task):
        result = await original(file, mime, task)
        if not next(answers):
            result["score"] = task.max_score - 1
        return result

    monkeypatch.setattr(checker, "check_work", flaky)
    r = (await _send(client, headers, quest["id"], _photo(full=True, confidence=95))).json()
    assert not r["passed"] and r["total_coins"] == 0


async def test_quest_rules_and_access(client):
    app.state.work_checker = checker = StubWorkChecker()
    await make_student()
    headers = await login(client)
    # тема не пройдена — квеста нет
    open_topic = (await client.post("/api/explain", data={"title": "проценты"}, headers=headers)).json()["id"]
    r = await client.post("/api/quests", json={"topic_id": open_topic}, headers=headers)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "topic_not_completed"

    topic_id = await _completed_topic(client, headers)
    quest = (await client.post("/api/quests", json={"topic_id": topic_id}, headers=headers)).json()

    checker.fail_next = True  # сбой модели — попытка не сгорает
    assert (await _send(client, headers, quest["id"], _photo(full=True, confidence=95))).status_code == 502
    assert (await client.get(f"/api/quests/{quest['id']}", headers=headers)).json()["attempts_left"] == 3

    for _ in range(3):
        await _send(client, headers, quest["id"], _photo(full=False, confidence=95))
    r = await _send(client, headers, quest["id"], _photo(full=True, confidence=95))
    assert r.status_code == 429 and r.json()["detail"]["code"] == "quest_attempts"
    assert (await client.get(f"/api/quests/{quest['id']}", headers=headers)).json()["answer"]  # попытки кончились — ключ виден

    await make_student(tg_id=6000)
    other = await login(client, 6000)
    assert (await client.get(f"/api/quests/{quest['id']}", headers=other)).status_code == 404
    assert (await _send(client, other, quest["id"], b"x")).status_code == 404
    assert (await client.post("/api/quests", json={"topic_id": topic_id}, headers=other)).status_code == 404
    parent = await login(client, KID_TG + 1)
    assert (await client.get("/api/quests", headers=parent)).status_code == 403
