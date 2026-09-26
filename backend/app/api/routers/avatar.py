"""Персонаж ученика: обмен очков на коины и магазин вещей. Только для самого ученика."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import api_error, current_user, get_session
from app.db.models import Student, User
from app.repositories.students import get_student
from app.services import avatar

router = APIRouter(prefix="/api/v1/avatar", tags=["avatar"])


async def current_student(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> Student:
    student = await get_student(session, user.id) if user.role == "student" else None
    if student is None:
        raise api_error(403, "not_student")
    return student


class ExchangeIn(BaseModel):
    points: int = Field(gt=0)


class ItemIn(BaseModel):
    item: str = Field(min_length=1, max_length=32)


class EquipIn(ItemIn):
    equipped: bool = True


@router.get("")
async def get_avatar(student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)):
    return await avatar.state(session, student)


@router.post("/exchange")
async def exchange(body: ExchangeIn, student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)):
    try:
        await avatar.exchange(session, student, body.points)
    except avatar.AvatarError as exc:
        raise api_error(exc.status, exc.code)
    return await avatar.state(session, student)


@router.post("/buy")
async def buy(body: ItemIn, student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)):
    try:
        await avatar.buy(session, student, body.item)
    except avatar.AvatarError as exc:
        raise api_error(exc.status, exc.code)
    return await avatar.state(session, student)


@router.post("/equip")
async def equip(body: EquipIn, student: Student = Depends(current_student), session: AsyncSession = Depends(get_session)):
    try:
        await avatar.equip(session, student, body.item, body.equipped)
    except avatar.AvatarError as exc:
        raise api_error(exc.status, exc.code)
    return await avatar.state(session, student)
