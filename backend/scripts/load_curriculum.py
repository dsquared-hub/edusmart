"""Загрузка школьной программы (предметы и темы) из JSON.

    python scripts/load_curriculum.py path/to/curriculum.json
    python scripts/load_curriculum.py            # образец app/data/curriculum_sample.json

Формат — как в образце. Повторный запуск безопасен: существующие темы обновляются.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal, dispose_db, init_db  # noqa: E402
from app.services.curriculum import SAMPLE, load_curriculum  # noqa: E402


async def main(path: Path) -> None:
    init_db()
    async with SessionLocal() as session:
        subjects, topics = await load_curriculum(session, json.loads(path.read_text(encoding="utf-8")))
    await dispose_db()
    print(f"Загружено: предметов +{subjects}, тем +{topics} ({path})")


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]) if len(sys.argv) > 1 else SAMPLE))
