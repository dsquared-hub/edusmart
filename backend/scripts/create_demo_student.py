"""Демо-ученик для входа на сайт без Telegram (логин + код).

    python scripts/create_demo_student.py                # логин demo, код 123456
    python scripts/create_demo_student.py anya 654321 "Аня"

Ученику сразу ставится согласие — только для локальной проверки, не для продакшена.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import hash_code  # noqa: E402
from app.db.models import User  # noqa: E402
from app.db.session import SessionLocal, dispose_db, init_db  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.repositories.students import create_student, get_student  # noqa: E402
from app.repositories.users import get_by_login  # noqa: E402


async def main(login: str, code: str, name: str) -> None:
    init_db()
    async with SessionLocal() as session:
        user = await get_by_login(session, login)
        if user is None:
            user = User(full_name=name, role="student", login=login)
            session.add(user)
            await session.flush()
            await create_student(session, user.id, consent=True, grade=5)
        student = await get_student(session, user.id)
        student.consent_confirmed = True
        student.consent_version = get_settings().policy_version  # только для локальной проверки
        user.access_code_hash = hash_code(code)
        user.failed_logins = 0
        user.locked_until = None
        await session.commit()
    await dispose_db()
    print(f"Готово. Вход на сайте: логин «{login}», код «{code}»")


if __name__ == "__main__":
    args = sys.argv[1:]
    asyncio.run(
        main(
            args[0] if len(args) > 0 else "demo",
            args[1] if len(args) > 1 else "123456",
            args[2] if len(args) > 2 else "Демо Ученик",
        )
    )
