"""Бан-лист в памяти (проверка на каждом апдейте без запроса к БД) + владелец.

Постоянное хранилище — таблица blocked_users (общая с сайтом).
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import blocks as blocks_repo


class SecurityManager:
    def __init__(self, owner_id: int | None = None):
        self.owner_id = owner_id
        self._blocked: set[int] = set()

    async def refresh(self, session: AsyncSession) -> None:
        self._blocked = await blocks_repo.blocked_ids(session)

    def is_blocked(self, telegram_id: int) -> bool:
        return telegram_id in self._blocked

    @property
    def blocked_count(self) -> int:
        return len(self._blocked)

    async def block(self, session: AsyncSession, telegram_id: int, reason: str | None = None) -> bool:
        """Блокирует пользователя. Владельца заблокировать нельзя."""
        if telegram_id == self.owner_id:
            return False
        created = await blocks_repo.block_user(session, telegram_id, reason)
        await session.commit()
        if created:
            self._blocked.add(telegram_id)
        return created

    async def unblock(self, session: AsyncSession, telegram_id: int) -> bool:
        removed = await blocks_repo.unblock_user(session, telegram_id)
        await session.commit()
        if removed:
            self._blocked.discard(telegram_id)
        return removed
