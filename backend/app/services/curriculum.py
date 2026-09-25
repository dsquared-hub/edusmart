"""Школьная программа: предметы и темы (Модуль 4) и привязка объяснений к темам.

Каталог загружается из JSON (scripts/load_curriculum.py). В репозитории — образец
(app/data/curriculum_sample.json); официальную программу нужно получить у
Министерства просвещения и загрузить тем же форматом.
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CurriculumSubject, CurriculumTopic
from app.services.rag import HashEmbedder

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "curriculum_sample.json"
MATCH_THRESHOLD = 0.3  # ниже — тема ученика не из программы (или не распознана)
_embedder = HashEmbedder()


async def load_curriculum(session: AsyncSession, data: dict) -> tuple[int, int]:
    """Идемпотентная загрузка: предмет — по (code, grade), тема — по русскому названию.
    Возвращает (добавлено предметов, добавлено тем)."""
    new_subjects = new_topics = 0
    for s in data.get("subjects", []):
        subject = await session.scalar(
            select(CurriculumSubject).where(CurriculumSubject.code == s["code"], CurriculumSubject.grade == s["grade"])
        )
        if subject is None:
            subject = CurriculumSubject(code=s["code"], grade=s["grade"])
            session.add(subject)
            new_subjects += 1
        subject.name_uz, subject.name_ru, subject.name_en = s["name"]["uz"], s["name"]["ru"], s["name"]["en"]
        await session.flush()
        existing = {
            t.name_ru: t
            for t in await session.scalars(select(CurriculumTopic).where(CurriculumTopic.subject_id == subject.id))
        }
        for order, names in enumerate(s.get("topics", []), start=1):
            topic = existing.get(names["ru"])
            if topic is None:
                topic = CurriculumTopic(subject_id=subject.id, grade=s["grade"], name_ru=names["ru"])
                session.add(topic)
                new_topics += 1
            topic.order, topic.name_uz, topic.name_en = order, names["uz"], names["en"]
    await session.commit()
    return new_subjects, new_topics


async def ensure_sample(session: AsyncSession) -> None:
    """Пустой каталог — загружаем образец, чтобы вечерний тест и ERS работали сразу."""
    if not await session.scalar(select(func.count(CurriculumSubject.id))):
        await load_curriculum(session, json.loads(SAMPLE.read_text(encoding="utf-8")))


async def match_topic(session: AsyncSession, title: str, subject: str | None, grade: int | None) -> int | None:
    """Ближайшая тема программы по названию (на всех трёх языках) в пределах класса
    и предмета. Локально, без ИИ: слова и их начала (дроби/дробей)."""
    stmt = select(CurriculumTopic, CurriculumSubject.code).join(CurriculumSubject)
    if grade:
        stmt = stmt.where(CurriculumTopic.grade == grade)
    if subject and subject != "other":
        stmt = stmt.where(CurriculumSubject.code == subject)
    rows = (await session.execute(stmt)).all()
    if not rows or not title.strip():
        return None
    [query] = await _embedder.embed([title])
    names = await _embedder.embed([f"{t.name_ru} {t.name_uz} {t.name_en}" for t, _ in rows])
    best, score = None, 0.0
    for (topic, _), vec in zip(rows, names):
        s = sum(a * b for a, b in zip(query, vec))
        if s > score:
            best, score = topic, s
    return best.id if best is not None and score >= MATCH_THRESHOLD else None


async def subject_topics(session: AsyncSession, subject_id: int) -> list[CurriculumTopic]:
    rows = await session.scalars(
        select(CurriculumTopic).where(CurriculumTopic.subject_id == subject_id).order_by(CurriculumTopic.order)
    )
    return list(rows)
