"""Заранее наполнить банк вопросов ДТМ, чтобы ученик не ждал сборки варианта.

    python scripts/dtm_bank.py                    # все предметы, ru и uz, до 90 вопросов на предмет
    python scripts/dtm_bank.py --target 60 --lang uz --subject math physics
    python scripts/dtm_bank.py --pause 8          # пауза между пачками, сек (бесплатный ключ Gemini)

Пачки идут по одной, с паузой — чтобы не упереться в лимит запросов ключа. Каждый вопрос
перепроверяется вторым запросом, в банк попадают только верные. Лимит ключа исчерпан —
скрипт останавливается; повторный запуск продолжит с того же места.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select  # noqa: E402

from app.db.models import DtmQuestion  # noqa: E402
from app.db.session import SessionLocal, dispose_db, init_db  # noqa: E402
from app.services.dtm import GEN_BATCH, SUBJECTS, generate_bank  # noqa: E402
from app.services.questions import QuotaExceeded, make_question_generator  # noqa: E402


async def main(target: int, langs: list[str], subjects: list[str], pause: float) -> None:
    init_db()
    generator = make_question_generator()
    try:
        for lang in langs:
            for code in subjects:
                subject = SUBJECTS[code]
                async with SessionLocal() as session:
                    have = await session.scalar(
                        select(func.count(DtmQuestion.id)).where(DtmQuestion.subject == code, DtmQuestion.lang == lang)
                    ) or 0
                    while have < target:
                        added = await generate_bank(session, generator, subject, lang, GEN_BATCH, offset=have // GEN_BATCH)
                        have += added
                        print(f"{lang} {code}: {have}/{target}", flush=True)
                        if not added:
                            break  # модель подряд не дала годных вопросов — к следующему предмету
                        await asyncio.sleep(pause)
    except QuotaExceeded:
        print("Лимит ключа Gemini исчерпан — запустите позже, продолжим с того же места.")
    finally:
        await dispose_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", type=int, default=90, help="вопросов на предмет и язык")
    parser.add_argument("--lang", nargs="+", default=["ru", "uz"], choices=["ru", "uz"])
    parser.add_argument("--subject", nargs="+", default=list(SUBJECTS), choices=list(SUBJECTS))
    parser.add_argument("--pause", type=float, default=5.0)
    args = parser.parse_args()
    asyncio.run(main(args.target, args.lang, args.subject, args.pause))
