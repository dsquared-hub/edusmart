"""Проверка SMS-шлюза: отправляет настоящий код входа на указанный номер.

    python scripts/sms_check.py 901234567
    python scripts/sms_check.py 901234567 --lang uz

Берёт настройки из .env (SMS_PROVIDER и ESKIZ_* или SMS_GATE_*). Текст — тот же,
что при входе на сайте (для Eskiz проверяется и одобрен ли шаблон). В базу ничего не пишется.
"""
from __future__ import annotations

import argparse
import asyncio
import secrets
import sys

from app.core.config import get_settings
from app.services import sms


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phone")
    parser.add_argument("--lang", default="ru", choices=sorted(sms.TEXT))
    args = parser.parse_args()

    settings = get_settings()
    required = {
        "eskiz": {"ESKIZ_EMAIL": settings.eskiz_email, "ESKIZ_PASSWORD": settings.eskiz_password},
        "smsgate": {"SMS_GATE_USER": settings.sms_gate_user, "SMS_GATE_PASSWORD": settings.sms_gate_password},
    }.get(settings.sms_provider)
    if required is None:
        print("SMS_PROVIDER=log — SMS не уйдёт, код будет только в логе. Поставьте в .env smsgate или eskiz.")
        return 1
    missing = [name for name, value in required.items() if not value]
    if missing:
        print(f"Заполните в .env: {', '.join(missing)}.")
        return 1

    phone = sms.normalize_phone(args.phone)
    text = sms.TEXT[args.lang].format(code=f"{secrets.randbelow(1_000_000):06d}")
    try:
        await sms.make_sender(settings).send(phone, text)
    except Exception as exc:
        print(f"Не отправлено: {exc}")
        return 1
    print(f"Отправлено на {phone}: {text}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
