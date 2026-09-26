"""Персонаж ученика: очки → коины → вещи; доступ только у самого ученика."""
from __future__ import annotations

import asyncio

from app.db.session import SessionLocal
from app.repositories.students import get_student
from app.services.avatar import CATALOG, stage_for
from test_api import KID_TG, login, make_student


async def give_points(user_id: int, points: int) -> None:
    async with SessionLocal() as s:
        student = await get_student(s, user_id)
        student.points = points
        await s.commit()


def test_stages_grow_with_level():
    assert [stage_for(level) for level in (1, 2, 3, 5, 6, 9, 10, 25)] == [
        "baby", "baby", "kid", "kid", "teen", "teen", "champion", "champion",
    ]


async def test_exchange_buy_equip(client):
    user_id = await make_student()
    headers = await login(client)
    await give_points(user_id, 250)  # уровень 3

    r = await client.get("/api/v1/avatar", headers=headers)
    body = r.json()
    assert r.status_code == 200
    assert (body["coins"], body["free_points"], body["level"], body["stage"]) == (0, 250, 3, "kid")
    assert body["owned"] == [] and body["equipped"] == {} and len(body["catalog"]) == len(CATALOG)

    # Обмен: кратно 10 и не больше свободных очков; уровень не падает
    for bad in (5, 15):
        r = await client.post("/api/v1/avatar/exchange", json={"points": bad}, headers=headers)
        assert r.status_code == 422
    r = await client.post("/api/v1/avatar/exchange", json={"points": 260}, headers=headers)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_enough_points"
    r = await client.post("/api/v1/avatar/exchange", json={"points": 200}, headers=headers)
    body = r.json()
    assert (body["coins"], body["free_points"], body["points"], body["level"]) == (20, 50, 250, 3)

    # Покупка: не хватает коинов, закрыто по уровню, неизвестная вещь
    r = await client.post("/api/v1/avatar/buy", json={"item": "hoodie"}, headers=headers)  # 80 коинов
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_enough_coins"
    r = await client.post("/api/v1/avatar/buy", json={"item": "crown"}, headers=headers)  # с 10 уровня
    assert r.status_code == 403 and r.json()["detail"]["code"] == "item_locked"
    r = await client.post("/api/v1/avatar/buy", json={"item": "nope"}, headers=headers)
    assert r.status_code == 404

    # Купил — списалось и сразу надето; вторая вещь того же слота заменяет первую
    await give_points(user_id, 1250)
    await client.post("/api/v1/avatar/exchange", json={"points": 1000}, headers=headers)
    r = await client.post("/api/v1/avatar/buy", json={"item": "cap"}, headers=headers)
    body = r.json()
    assert body["coins"] == 120 - 30 and body["owned"] == ["cap"] and body["equipped"] == {"hat": "cap"}
    r = await client.post("/api/v1/avatar/buy", json={"item": "cap"}, headers=headers)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "item_owned"
    body = (await client.post("/api/v1/avatar/buy", json={"item": "headphones"}, headers=headers)).json()
    assert body["equipped"] == {"hat": "headphones"} and body["coins"] == 30

    # Надеть/снять только своё
    body = (await client.post("/api/v1/avatar/equip", json={"item": "cap"}, headers=headers)).json()
    assert body["equipped"] == {"hat": "cap"}
    body = (await client.post("/api/v1/avatar/equip", json={"item": "cap", "equipped": False}, headers=headers)).json()
    assert body["equipped"] == {}
    r = await client.post("/api/v1/avatar/equip", json={"item": "tuxedo"}, headers=headers)
    assert r.status_code == 404


async def test_parallel_buys_do_not_overspend(client):
    user_id = await make_student()
    headers = await login(client)
    await give_points(user_id, 300)
    await client.post("/api/v1/avatar/exchange", json={"points": 300}, headers=headers)  # 30 коинов — на одну кепку

    results = await asyncio.gather(
        client.post("/api/v1/avatar/buy", json={"item": "cap"}, headers=headers),
        client.post("/api/v1/avatar/buy", json={"item": "scarf"}, headers=headers),
    )
    assert sorted(r.status_code for r in results) == [200, 409]
    body = (await client.get("/api/v1/avatar", headers=headers)).json()
    assert body["coins"] == 0 and len(body["owned"]) == 1


async def test_avatar_is_only_for_the_student(client):
    await make_student()
    for path, method, payload in (
        ("/api/v1/avatar", "get", None),
        ("/api/v1/avatar/exchange", "post", {"points": 10}),
        ("/api/v1/avatar/buy", "post", {"item": "cap"}),
        ("/api/v1/avatar/equip", "post", {"item": "cap"}),
    ):
        r = await client.request(method, path, json=payload)
        assert r.status_code == 401, path
        parent = await login(client, KID_TG + 1)  # мама ребёнка — не ученик
        r = await client.request(method, path, json=payload, headers=parent)
        assert r.status_code == 403 and r.json()["detail"]["code"] == "not_student", path
