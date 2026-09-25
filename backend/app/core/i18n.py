"""Переводы: app/locales/<lang>.json — ru, uz (латиница), en.

t("key", name="Аня")          — язык текущего пользователя (ContextVar)
t("key", "uz", name="Аня")    — явно указанный язык (рассылки, уведомления)

Бот выставляет язык на каждый апдейт в мидлвари (set_current_lang), поэтому
хендлеры и клавиатуры не передают язык вручную. Нет ключа в выбранном
языке — берём русский, затем сам ключ.
"""
from __future__ import annotations

import json
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"
DEFAULT_LANG = "ru"
SUPPORTED_LANGS = ("ru", "uz", "en")

_current_lang: ContextVar[str] = ContextVar("current_lang", default=DEFAULT_LANG)


@lru_cache
def _messages(lang: str) -> dict[str, str]:
    path = LOCALES_DIR / f"{lang}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_lang(lang: str | None) -> str:
    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


def lang_from_telegram(language_code: str | None) -> str:
    """Язык нового пользователя по настройкам его Telegram."""
    code = (language_code or "").lower()
    if code.startswith("uz"):
        return "uz"
    if code.startswith("en"):
        return "en"
    return DEFAULT_LANG


def set_current_lang(lang: str | None) -> None:
    _current_lang.set(normalize_lang(lang))


def t(key: str, lang: str | None = None, **kwargs) -> str:
    lang = normalize_lang(lang or _current_lang.get())
    msg = _messages(lang).get(key) or _messages(DEFAULT_LANG).get(key) or key
    return msg.format(**kwargs) if kwargs else msg
