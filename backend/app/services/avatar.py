"""Персонаж ученика и магазин: очки → коины → вещи для персонажа.

Очки копятся за учёбу и определяют уровень. Свободные очки (ещё не обменянные)
меняются на коины по курсу POINTS_PER_COIN; уровень от обмена не падает. За коины
покупаются вещи — по одной на слот можно надеть. Персонаж растёт вместе с уровнем
(стадии STAGES), а часть вещей открывается только с определённого уровня.

Каталог живёт в коде: названия и картинки — на сайте (web/messages, Avatar.tsx).
Коины и очки списываются одним UPDATE с условием — двойной клик не уведёт баланс в минус.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Student, StudentItem
from app.services.gamification import level_for

POINTS_PER_COIN = 10
MAX_EXCHANGE = 100_000

SLOTS = ("hat", "outfit", "glasses", "extra", "background")

# Стадии роста персонажа: (с какого уровня, код стадии)
STAGES = ((1, "baby"), (3, "kid"), (6, "teen"), (10, "champion"))


@dataclass(frozen=True)
class Item:
    code: str
    slot: str
    price: int
    min_level: int = 1


CATALOG: dict[str, Item] = {
    item.code: item
    for item in (
        # Головные уборы
        Item("cap", "hat", 30),
        Item("headphones", "hat", 60, 2),
        Item("wizard_hat", "hat", 120, 4),
        Item("grad_cap", "hat", 180, 6),
        Item("crown", "hat", 300, 10),
        # Одежда и костюмы
        Item("tshirt", "outfit", 40),
        Item("hoodie", "outfit", 80, 2),
        Item("school_uniform", "outfit", 100, 3),
        Item("tuxedo", "outfit", 150, 4),
        Item("superhero", "outfit", 220, 5),
        Item("astronaut", "outfit", 300, 7),
        Item("knight", "outfit", 380, 9),
        # Очки
        Item("round_glasses", "glasses", 40),
        Item("sunglasses", "glasses", 60, 2),
        Item("star_glasses", "glasses", 90, 4),
        # Аксессуары
        Item("scarf", "extra", 30),
        Item("backpack", "extra", 70, 2),
        Item("cape", "extra", 160, 5),
        Item("medal", "extra", 240, 8),
        # Фон
        Item("park", "background", 50),
        Item("sea", "background", 120, 3),
        Item("classroom", "background", 80, 2),
        Item("space", "background", 250, 6),
    )
}


class AvatarError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


def stage_for(level: int) -> str:
    return [code for start, code in STAGES if level >= start][-1]


def next_stage_level(level: int) -> int | None:
    return next((start for start, _ in STAGES if start > level), None)


def free_points(student: Student) -> int:
    return max(0, (student.points or 0) - (student.points_exchanged or 0))


async def state(session: AsyncSession, student: Student) -> dict:
    await session.refresh(student)
    items = (await session.scalars(select(StudentItem).where(StudentItem.user_id == student.user_id))).all()
    level = level_for(student.points or 0)
    return {
        "coins": student.coins or 0,
        "points": student.points or 0,
        "free_points": free_points(student),
        "points_per_coin": POINTS_PER_COIN,
        "level": level,
        "stage": stage_for(level),
        "next_stage_level": next_stage_level(level),
        "owned": sorted(i.item_code for i in items if i.item_code in CATALOG),
        "equipped": {CATALOG[i.item_code].slot: i.item_code for i in items if i.equipped and i.item_code in CATALOG},
        "catalog": [
            {"code": it.code, "slot": it.slot, "price": it.price, "min_level": it.min_level} for it in CATALOG.values()
        ],
    }


async def exchange(session: AsyncSession, student: Student, points: int) -> int:
    """Обмен свободных очков на коины; points — кратно курсу. Возвращает полученные коины."""
    if points < POINTS_PER_COIN or points > MAX_EXCHANGE or points % POINTS_PER_COIN:
        raise AvatarError("bad_exchange", 422)
    coins = points // POINTS_PER_COIN
    result = await session.execute(
        update(Student)
        .where(Student.user_id == student.user_id, Student.points - Student.points_exchanged >= points)
        .values(points_exchanged=Student.points_exchanged + points, coins=Student.coins + coins)
    )
    if result.rowcount != 1:
        await session.rollback()
        raise AvatarError("not_enough_points", 409)
    await session.commit()
    return coins


async def _equip(session: AsyncSession, user_id: int, item: Item) -> None:
    """Надеть вещь: в слоте остаётся только она."""
    same_slot = [code for code, it in CATALOG.items() if it.slot == item.slot]
    await session.execute(
        update(StudentItem)
        .where(StudentItem.user_id == user_id, StudentItem.item_code.in_(same_slot))
        .values(equipped=StudentItem.item_code == item.code)
    )


async def buy(session: AsyncSession, student: Student, code: str) -> None:
    item = CATALOG.get(code)
    if item is None:
        raise AvatarError("unknown_item", 404)
    if level_for(student.points or 0) < item.min_level:
        raise AvatarError("item_locked", 403)
    owned = await session.scalar(
        select(StudentItem.id).where(StudentItem.user_id == student.user_id, StudentItem.item_code == code)
    )
    if owned is not None:
        raise AvatarError("item_owned", 409)
    result = await session.execute(
        update(Student)
        .where(Student.user_id == student.user_id, Student.coins >= item.price)
        .values(coins=Student.coins - item.price)
    )
    if result.rowcount != 1:
        await session.rollback()
        raise AvatarError("not_enough_coins", 409)
    session.add(StudentItem(user_id=student.user_id, item_code=code, equipped=False))
    try:
        await session.flush()
    except IntegrityError:  # та же вещь куплена параллельным запросом — коины не списываем
        await session.rollback()
        raise AvatarError("item_owned", 409) from None
    await _equip(session, student.user_id, item)  # купил — сразу надел
    await session.commit()


async def equip(session: AsyncSession, student: Student, code: str, on: bool) -> None:
    item = CATALOG.get(code)
    row = await session.scalar(
        select(StudentItem).where(StudentItem.user_id == student.user_id, StudentItem.item_code == code)
    )
    if item is None or row is None:
        raise AvatarError("item_not_owned", 404)
    if on:
        await _equip(session, student.user_id, item)
    else:
        row.equipped = False
    await session.commit()
