"""Переводы бота: одинаковые ключи и плейсхолдеры во всех языках."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.core.i18n import LOCALES_DIR, lang_from_telegram, set_current_lang, t

PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _load(lang: str) -> dict[str, str]:
    return json.loads((LOCALES_DIR / f"{lang}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("lang", ["uz", "en"])
def test_same_keys_and_placeholders_as_russian(lang):
    ru, other = _load("ru"), _load(lang)
    assert set(other) == set(ru), set(ru) ^ set(other)
    for key, text in ru.items():
        assert set(PLACEHOLDER.findall(other[key])) == set(PLACEHOLDER.findall(text)), key


def test_web_messages_have_same_keys():
    web = Path(__file__).resolve().parents[2] / "web" / "messages"

    def keys(node, prefix=""):
        if isinstance(node, dict):
            return {k for key, v in node.items() for k in keys(v, f"{prefix}{key}.")}
        return {prefix.rstrip(".")}

    ru = keys(json.loads((web / "ru.json").read_text(encoding="utf-8")))
    for lang in ("uz", "en"):
        assert keys(json.loads((web / f"{lang}.json").read_text(encoding="utf-8"))) == ru, lang


def test_current_language_and_fallback():
    set_current_lang("en")
    assert t("btn_help") == "📘 I don't get it"
    assert t("btn_help", "uz") == "📘 Mavzuni tushunmadim"
    set_current_lang("xx")  # неизвестный — русский
    assert t("btn_help") == "📘 Не понял тему"
    assert lang_from_telegram("uz-UZ") == "uz" and lang_from_telegram(None) == "ru"
