"""PvP-дуэли: одни вопросы, серверный таймер, ответы — только после конца, коины один раз."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.core.timeutil import utcnow
from app.db.models import Duel, Event, Student
from app.db.session import SessionLocal
from test_api import KID_TG, login, make_student

FRIEND_TG = 6000


async def _correct(duel_id: int) -> list[int]:
    async with SessionLocal() as s:
        return [q["correct"] for q in (await s.get(Duel, duel_id)).questions]


async def _play(client, headers, duel_id: int, right: list[int], wrong: set[int] = frozenset()) -> None:
    for n in range(5):
        q = (await client.post(f"/api/duels/{duel_id}/next", headers=headers)).json()["question"]
        assert q["n"] == n and "correct" not in q and q["seconds_left"] > 25
        option = (right[n] + 1) % len(q["options"]) if n in wrong else right[n]
        r = await client.post(f"/api/duels/{duel_id}/answer", json={"n": n, "option": option}, headers=headers)
        assert r.status_code == 200, r.text


async def _coins(user_id: int) -> int:
    async with SessionLocal() as s:
        return (await s.get(Student, user_id)).coins


async def test_duel_by_code_full_game(client):
    me_id = await make_student()
    friend_id = await make_student(tg_id=FRIEND_TG)
    me, friend = await login(client), await login(client, FRIEND_TG)

    duel = (await client.post("/api/duels", json={"topic": "дроби", "subject": "math"}, headers=me)).json()
    assert duel["status"] == "open" and len(duel["code"]) == 6 and duel["i_am_creator"]
    right = await _correct(duel["id"])

    await _play(client, me, duel["id"], right, wrong={4})  # 4 из 5
    # пока друг не сыграл — ни его счёта, ни верных ответов
    mine = (await client.get(f"/api/duels/{duel['id']}", headers=me)).json()
    assert mine["me"] == {**mine["me"], "correct": 4, "done": True} and mine["them"] is None and "review" not in mine
    assert (await client.get(f"/api/duels/{duel['id']}", headers=friend)).status_code == 404  # ещё не участник

    joined = (await client.post("/api/duels/join", json={"code": duel["code"].lower()}, headers=friend)).json()
    assert joined["status"] == "active" and joined["code"] is None and joined["opponent"] == "Аня"
    await _play(client, friend, duel["id"], right)  # 5 из 5

    final = (await client.get(f"/api/duels/{duel['id']}", headers=me)).json()
    assert final["status"] == "finished" and final["winner"] == "them" and final["reward"] == 1
    assert final["them"]["correct"] == 5 and final["review"][4]["mine"] != final["review"][4]["correct"]
    assert (await client.get(f"/api/duels/{duel['id']}", headers=friend)).json()["winner"] == "me"
    assert await _coins(me_id) == 1 and await _coins(friend_id) == 5
    async with SessionLocal() as s:
        assert await s.scalar(select(Event.type).where(Event.type == "duel_finished")) == "duel_finished"

    # после конца — ни вопросов, ни ответов
    assert (await client.post(f"/api/duels/{duel['id']}/next", headers=me)).status_code == 409


async def test_server_timer_and_order(client):
    await make_student()
    me = await login(client)
    duel = (await client.post("/api/duels", json={"topic": "проценты"}, headers=me)).json()
    right = await _correct(duel["id"])
    assert (await client.post(f"/api/duels/{duel['id']}/answer", json={"n": 0, "option": right[0]}, headers=me)).status_code == 409
    await client.post(f"/api/duels/{duel['id']}/next", headers=me)
    async with SessionLocal() as s:  # «думал» 40 секунд
        d = await s.get(Duel, duel["id"])
        res = {**d.results}
        mine = dict(res[str(d.creator_id)])
        mine["shown_at"] = (utcnow() - timedelta(seconds=40)).isoformat()
        res[str(d.creator_id)] = mine
        d.results = res
        await s.commit()
    r = (await client.post(f"/api/duels/{duel['id']}/answer", json={"n": 0, "option": right[0]}, headers=me)).json()
    assert r["ok"] is False  # опоздал — верный ответ не засчитан
    r = await client.post(f"/api/duels/{duel['id']}/answer", json={"n": 0, "option": right[0]}, headers=me)
    assert r.status_code == 409  # второй раз на тот же вопрос нельзя


async def test_random_opponent_and_race(client):
    await make_student()
    await make_student(tg_id=FRIEND_TG)
    await make_student(tg_id=7000)
    me, friend, third = await login(client), await login(client, FRIEND_TG), await login(client, 7000)
    r = await client.post("/api/duels/random", headers=friend)
    assert r.status_code == 404 and r.json()["detail"]["code"] == "no_open_duels"

    private = (await client.post("/api/duels", json={"topic": "дроби"}, headers=me)).json()
    public = (await client.post("/api/duels", json={"topic": "площадь", "public": True}, headers=me)).json()
    assert (await client.post("/api/duels/random", headers=me)).status_code == 404  # свой вызов себе не выдаётся
    got = (await client.post("/api/duels/random", headers=friend)).json()
    assert got["id"] == public["id"]  # закрытый вызов — только по коду
    r = await client.post("/api/duels/join", json={"code": public["code"]}, headers=third)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "duel_taken"
    assert (await client.post("/api/duels/join", json={"code": "ZZZZZZ"}, headers=third)).status_code == 404

    async with SessionLocal() as s:
        (await s.get(Duel, private["id"])).expires_at = utcnow() - timedelta(minutes=1)
        await s.commit()
    r = await client.post("/api/duels/join", json={"code": private["code"]}, headers=third)
    assert r.status_code == 410 and r.json()["detail"]["code"] == "duel_expired"


async def test_duel_access_and_limit(client):
    await make_student()
    me = await login(client)
    duel = (await client.post("/api/duels", json={"topic": "дроби"}, headers=me)).json()
    progress = (await client.get("/api/progress", headers=me)).json()
    assert progress["explanations_left_today"] == progress["daily_limit"] - 1  # создание — одна попытка

    await make_student(tg_id=FRIEND_TG)
    stranger = await login(client, FRIEND_TG)
    for method, path in (("get", ""), ("post", "/next")):
        r = await getattr(client, method)(f"/api/duels/{duel['id']}{path}", headers=stranger)
        assert r.status_code == 404
    parent = await login(client, KID_TG + 1)
    assert (await client.post("/api/duels", json={"topic": "x"}, headers=parent)).status_code == 403
