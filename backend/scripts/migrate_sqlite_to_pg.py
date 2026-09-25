"""Перенос данных старого бота (SQLite) в новую базу (PostgreSQL).

Запуск (из папки backend, после `alembic upgrade head`):
    python scripts/migrate_sqlite_to_pg.py path/to/education_bot.db
    python scripts/migrate_sqlite_to_pg.py old.db --dry-run    # только посчитать

Целевая база — из DATABASE_URL. Скрипт запускается один раз на пустую базу.

Что происходит:
- users.id был Telegram ID → становится users.telegram_id, id выдаётся новый;
- все ссылки (ученики, привязки, лимиты, дни активности) пересчитываются на новые id;
- очки, серии, коды семьи, согласия, закрытые темы и ошибки сохраняются;
- бан-лист владельца переносится как есть (по Telegram ID);
- незавершённые темы → status="abandoned": их шаги жили в памяти старого бота
  и не сохранились, продолжить их всё равно нельзя.
"""
from __future__ import annotations

import argparse
import asyncio
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.core.timeutil import utcnow  # noqa: E402
from app.db.models import (  # noqa: E402
    ActivityDay,
    BlockedUser,
    DailyUsage,
    ParentLink,
    StepAttempt,
    Student,
    TeacherLink,
    Topic,
    User,
)
from app.db.session import SessionLocal, dispose_db, init_db  # noqa: E402


def _dt(value) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", ""))


def _d(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _rows(conn: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not exists:
        return []
    return conn.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608 — имя из белого списка


async def migrate(sqlite_path: Path, dry_run: bool = False, database_url: str | None = None) -> dict:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    init_db(database_url)
    stats: dict[str, int] = {}

    async with SessionLocal() as session:
        if await session.scalar(select(func.count(User.id))):
            raise SystemExit("Целевая база не пустая — перенос делается один раз на пустую базу.")

        # users: старый id = Telegram ID
        user_map: dict[int, int] = {}
        for row in _rows(conn, "users"):
            user = User(
                telegram_id=row["id"],
                username=row["username"],
                full_name=row["full_name"],
                role=row["role"],
                created_at=_dt(row["created_at"]) or utcnow(),
            )
            session.add(user)
            await session.flush()
            user_map[row["id"]] = user.id
        stats["users"] = len(user_map)

        students = 0
        for row in _rows(conn, "students"):
            if row["user_id"] not in user_map:
                continue
            session.add(
                Student(
                    user_id=user_map[row["user_id"]],
                    points=row["points"] or 0,
                    streak=row["streak"] or 0,
                    last_active_on=_d(row["last_active_on"]),
                    family_code=row["family_code"],
                    consent_confirmed=bool(row["consent_confirmed"]),
                    # согласие давали на старую (черновую) политику — понадобится новое
                    consent_version="legacy" if row["consent_confirmed"] else None,
                    created_at=_dt(row["created_at"]) or utcnow(),
                )
            )
            students += 1
        await session.flush()
        stats["students"] = students

        for table, model, owner in (
            ("parent_links", ParentLink, "parent_user_id"),
            ("teacher_links", TeacherLink, "teacher_user_id"),
        ):
            count = 0
            for row in _rows(conn, table):
                if row[owner] not in user_map or row["student_user_id"] not in user_map:
                    continue
                session.add(
                    model(
                        **{owner: user_map[row[owner]]},
                        student_user_id=user_map[row["student_user_id"]],
                        created_at=_dt(row["created_at"]) or utcnow(),
                    )
                )
                count += 1
            stats[table] = count
        await session.flush()

        topic_map: dict[int, int] = {}
        abandoned = 0
        for row in _rows(conn, "topics"):
            if row["student_user_id"] not in user_map:
                continue
            completed = row["status"] == "completed"
            abandoned += 0 if completed else 1
            created = _dt(row["created_at"]) or utcnow()
            topic = Topic(
                student_user_id=user_map[row["student_user_id"]],
                title=row["title"],
                source="bot",
                status="completed" if completed else "abandoned",
                steps=[],  # содержимое шагов старый бот не хранил
                current_step=0,
                points_earned=row["points_earned"] or 0,
                created_at=created,
                updated_at=_dt(row["completed_at"]) or created,
                completed_at=_dt(row["completed_at"]),
            )
            session.add(topic)
            await session.flush()
            topic_map[row["id"]] = topic.id
        stats["topics"] = len(topic_map)
        stats["topics_abandoned"] = abandoned

        attempts = 0
        for row in _rows(conn, "step_attempts"):
            if row["topic_id"] not in topic_map:
                continue
            session.add(
                StepAttempt(
                    topic_id=topic_map[row["topic_id"]],
                    step_index=row["step_index"] or 0,
                    wrong_count=row["wrong_count"] or 0,
                    success=bool(row["success"]),
                    created_at=_dt(row["created_at"]) or utcnow(),
                )
            )
            attempts += 1
        stats["step_attempts"] = attempts

        for table, model in (("daily_usage", DailyUsage), ("activity_days", ActivityDay)):
            count = 0
            for row in _rows(conn, table):
                if row["user_id"] not in user_map:
                    continue
                fields = {"user_id": user_map[row["user_id"]], "date": _d(row["date"])}
                if model is DailyUsage:
                    fields["explanations"] = row["explanations"] or 0
                session.add(model(**fields))
                count += 1
            stats[table] = count

        # blocked_users (появилась в старом боте позже): user_id там — Telegram ID
        blocked = 0
        for row in _rows(conn, "blocked_users"):
            session.add(
                BlockedUser(
                    telegram_id=row["user_id"],
                    reason=row["reason"],
                    created_at=_dt(row["created_at"]) or utcnow(),
                )
            )
            blocked += 1
        stats["blocked_users"] = blocked

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    conn.close()
    await dispose_db()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sqlite_path", type=Path, help="старый файл education_bot.db")
    parser.add_argument("--dry-run", action="store_true", help="посчитать, но не сохранять")
    args = parser.parse_args()
    if not args.sqlite_path.exists():
        raise SystemExit(f"Файл не найден: {args.sqlite_path}")

    stats = asyncio.run(migrate(args.sqlite_path, args.dry_run))
    title = "Проверка (ничего не сохранено)" if args.dry_run else "Перенесено"
    print(f"{title}:")
    for key, value in stats.items():
        print(f"  {key:18} {value}")


if __name__ == "__main__":
    main()
