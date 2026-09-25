"""Перенос данных из SQLite старого бота."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from sqlalchemy import select

from app.db import session as db_session
from app.db.models import ParentLink, StepAttempt, Student, Topic
from app.repositories.blocks import is_blocked
from app.repositories.students import weak_topics
from app.repositories.users import get_by_telegram

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from migrate_sqlite_to_pg import migrate  # noqa: E402

# Схема, которую создавал старый бот (SQLAlchemy create_all на SQLite)
OLD_SCHEMA = """
CREATE TABLE users (id BIGINT PRIMARY KEY, username VARCHAR(64), full_name VARCHAR(255),
    role VARCHAR(20), created_at DATETIME);
CREATE TABLE students (user_id BIGINT PRIMARY KEY REFERENCES users(id), points INTEGER,
    streak INTEGER, last_active_on DATE, family_code VARCHAR(6) UNIQUE,
    consent_confirmed BOOLEAN, created_at DATETIME);
CREATE TABLE parent_links (id INTEGER PRIMARY KEY, parent_user_id BIGINT, student_user_id BIGINT,
    created_at DATETIME);
CREATE TABLE teacher_links (id INTEGER PRIMARY KEY, teacher_user_id BIGINT, student_user_id BIGINT,
    created_at DATETIME);
CREATE TABLE topics (id INTEGER PRIMARY KEY, student_user_id BIGINT, title VARCHAR(255),
    status VARCHAR(16), total_steps INTEGER, points_earned INTEGER, created_at DATETIME,
    completed_at DATETIME);
CREATE TABLE step_attempts (id INTEGER PRIMARY KEY, topic_id INTEGER, step_index INTEGER,
    wrong_count INTEGER, success BOOLEAN, created_at DATETIME);
CREATE TABLE daily_usage (id INTEGER PRIMARY KEY, user_id BIGINT, date DATE, explanations INTEGER);
CREATE TABLE activity_days (id INTEGER PRIMARY KEY, user_id BIGINT, date DATE);
CREATE TABLE blocked_users (user_id BIGINT PRIMARY KEY, reason VARCHAR(255), created_at DATETIME);
"""

KID_TG, MOM_TG, TEACHER_TG = 5_000_000_001, 5_000_000_002, 5_000_000_003


def _make_old_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(OLD_SCHEMA)
    ts = "2026-09-01 10:00:00.123456"
    conn.executemany(
        "INSERT INTO users VALUES (?,?,?,?,?)",
        [
            (KID_TG, "kid", "Аня", "student", ts),
            (MOM_TG, "mom", "Мама", "parent", ts),
            (TEACHER_TG, None, "Учитель", "teacher", ts),
        ],
    )
    conn.execute(
        "INSERT INTO students VALUES (?,?,?,?,?,?,?)",
        (KID_TG, 130, 4, "2026-09-20", "123456", 1, ts),
    )
    conn.execute("INSERT INTO parent_links VALUES (1,?,?,?)", (MOM_TG, KID_TG, ts))
    conn.execute("INSERT INTO teacher_links VALUES (1,?,?,?)", (TEACHER_TG, KID_TG, ts))
    conn.execute(
        "INSERT INTO topics VALUES (7,?,?,?,?,?,?,?)",
        (KID_TG, "дроби", "completed", 4, 40, ts, "2026-09-01 10:20:00"),
    )
    conn.execute(
        "INSERT INTO topics VALUES (8,?,?,?,?,?,?,?)",
        (KID_TG, "проценты", "in_progress", 3, 0, ts, None),
    )
    conn.execute("INSERT INTO step_attempts VALUES (1,7,0,2,1,?)", (ts,))
    conn.execute("INSERT INTO daily_usage VALUES (1,?,?,?)", (KID_TG, "2026-09-20", 3))
    conn.execute("INSERT INTO activity_days VALUES (1,?,?)", (KID_TG, "2026-09-20"))
    conn.execute("INSERT INTO blocked_users VALUES (?,?,?)", (9_000_000_001, "спам", ts))
    conn.commit()
    conn.close()


async def test_migrate_old_sqlite(tmp_path, db, db_url):
    old = tmp_path / "education_bot.db"
    _make_old_db(old)
    await db_session.dispose_db()

    stats = await migrate(old, database_url=db_url)
    assert stats["users"] == 3 and stats["students"] == 1
    assert stats["topics"] == 2 and stats["topics_abandoned"] == 1

    db_session.init_db(db_url)
    async with db_session.SessionLocal() as s:
        kid = await get_by_telegram(s, KID_TG)
        assert kid is not None and kid.id != KID_TG and kid.full_name == "Аня"
        student = await s.get(Student, kid.id)
        assert (student.points, student.streak, student.family_code) == (130, 4, "123456")
        assert student.consent_confirmed

        mom = await get_by_telegram(s, MOM_TG)
        link = await s.scalar(select(ParentLink))
        assert (link.parent_user_id, link.student_user_id) == (mom.id, kid.id)

        topics = {t.title: t for t in await s.scalars(select(Topic))}
        assert topics["дроби"].status == "completed" and topics["дроби"].points_earned == 40
        assert topics["проценты"].status == "abandoned"
        attempt = await s.scalar(select(StepAttempt))
        assert attempt.topic_id == topics["дроби"].id
        # Статистика учителя продолжает работать на перенесённых данных
        assert await weak_topics(s, kid.id) == [("дроби", 2)]
        assert await is_blocked(s, 9_000_000_001)


async def test_migrate_refuses_non_empty_target(tmp_path, db, db_url):
    old = tmp_path / "education_bot.db"
    _make_old_db(old)
    await db_session.dispose_db()
    await migrate(old, database_url=db_url)
    try:
        await migrate(old, database_url=db_url)
    except SystemExit as exc:
        assert "не пустая" in str(exc)
    else:
        raise AssertionError("повторный перенос должен быть запрещён")
