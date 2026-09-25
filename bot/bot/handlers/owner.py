"""Команды владельца: /myid, /block, /unblock, /status."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from app.core.i18n import t
from app.db.session import SessionLocal
from app.repositories.blocks import count_students, count_users
from app.services.explain import ExplainService
from bot.security import SecurityManager

router = Router()


def _parse_target(args: str | None) -> tuple[int | None, str | None]:
    """«<id> [причина]» → (id, причина)."""
    if not args:
        return None, None
    first, _, rest = args.strip().partition(" ")
    return (int(first) if first.isdigit() else None), (rest.strip() or None)


async def _deny_if_not_owner(message: Message, security: SecurityManager) -> bool:
    """True — доступ запрещён и ответ уже отправлен."""
    if security.owner_id is None:
        await message.answer(t("owner_not_configured"))
        return True
    if message.from_user.id != security.owner_id:
        await message.answer(t("owner_only"))
        return True
    return False


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    await message.answer(t("myid_text", id=message.from_user.id))


@router.message(Command("block"))
async def cmd_block(message: Message, command: CommandObject, security: SecurityManager) -> None:
    if await _deny_if_not_owner(message, security):
        return
    target, reason = _parse_target(command.args)
    if target is None:
        await message.answer(t("block_usage"))
        return
    if target == security.owner_id:
        await message.answer(t("block_owner"))
        return
    async with SessionLocal() as session:
        created = await security.block(session, target, reason[:255] if reason else None)
    await message.answer(t("blocked_ok" if created else "block_already", id=target))


@router.message(Command("unblock"))
async def cmd_unblock(message: Message, command: CommandObject, security: SecurityManager) -> None:
    if await _deny_if_not_owner(message, security):
        return
    target, _ = _parse_target(command.args)
    if target is None:
        await message.answer(t("unblock_usage"))
        return
    async with SessionLocal() as session:
        removed = await security.unblock(session, target)
    await message.answer(t("unblocked_ok" if removed else "block_not_found", id=target))


@router.message(Command("status"))
async def cmd_status(message: Message, security: SecurityManager, explain: ExplainService) -> None:
    if await _deny_if_not_owner(message, security):
        return
    async with SessionLocal() as session:
        users = await count_users(session)
        students = await count_students(session)
    await message.answer(
        t(
            "status_title",
            users=users,
            students=students,
            blocked=security.blocked_count,
            model=explain.settings.gemini_model,
            limit=explain.settings.daily_explain_limit,
        )
    )
