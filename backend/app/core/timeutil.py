"""Время: в БД храним наивное UTC, «сегодня» считаем в таймзоне школы."""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_now() -> datetime:
    return datetime.now(ZoneInfo(get_settings().timezone))


def local_today() -> date:
    return local_now().date()
