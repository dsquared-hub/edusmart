"""Настройки из общего .env (корень монорепозитория) и переменных окружения."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> корень монорепозитория
ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    bot_token: str = ""
    bot_username: str = ""  # без @, нужен для Login Widget
    owner_id: int | None = None  # Telegram ID владельца: /block, /unblock, /status
    flood_max_messages: int = 6  # не больше N апдейтов…
    flood_window_seconds: float = 3.0  # …за столько секунд

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-lite-latest"
    gemini_fake: bool = False  # заглушка вместо Gemini (тесты, демо без ключа)
    # Второй независимый запрос проверяет правильные ответы (+ проверка арифметики в коде)
    verify_explanations: bool = True

    # База
    database_url: str = "sqlite+aiosqlite:///./education.db"

    # Сайт и API
    web_url: str = "http://localhost:3000"
    jwt_secret: str = "change-me"
    jwt_ttl_hours: int = 24 * 30
    cors_origins: str = "http://localhost:3000"
    max_photo_mb: int = 5

    # Правила
    daily_explain_limit: int = 20
    daily_simplify_limit: int = 60  # «Объясни проще» в день (каждое — платный запрос)
    simplify_per_step: int = 3  # сколько раз можно упростить один шаг
    points_per_step: int = 10  # за верный ответ с первой попытки
    points_second_try: int = 5  # со второй; дальше — 0 (угадыванием очки не заработать)
    timezone: str = "Asia/Tashkent"
    events_poll_seconds: float = 5.0

    # Academic Copilot: ИИ-проверка рукописных работ (Модуль 5.1)
    media_dir: str = str(ROOT_DIR / "backend" / "media")  # фото работ (не в git; в Docker — том)
    check_max_files: int = 40
    check_max_file_mb: int = 10
    check_worker: bool = True  # обработчик очереди внутри API; в проде можно вынести отдельно
    check_concurrency: int = 4  # работ одновременно: класс из 30 — за ~2–3 минуты
    check_timeout_seconds: float = 60.0
    check_max_attempts: int = 3
    # Пороги уверенности ИИ: ≥ one_click — подтверждение в 1 клик,
    # ≥ review — «Проверьте» (после открытия), ниже — только ручная проверка
    check_one_click_confidence: int = 90
    check_review_confidence: int = 70

    # Academic Copilot: генерация уроков по учебнику, RAG (Модуль 5.2)
    embed_model: str = "gemini-embedding-001"
    embed_dims: int = 768
    rag_top_k: int = 8
    textbook_max_mb: int = 50
    materials_timeout_seconds: float = 45.0  # цель ТЗ — ≤30 с на генерацию

    # Модуль 4: вечерний тест и Exam Readiness Score
    curriculum_autoload: bool = True  # пустой каталог программы → загрузить образец
    evening_start: str = "17:00"  # окно теста по Ташкенту
    evening_end: str = "22:00"
    evening_review_days: str = "3,7,14"  # интервальное повторение: темы N дней назад
    freezes_per_week: int = 2  # бесплатные «заморозки» серии
    points_correction: int = 5  # монеты за исправление после объяснения
    # ERS = wM·M + wS·S + wV·V + wR·R — веса меняются без релиза (через .env)
    ers_weights: str = "0.50,0.25,0.15,0.10"
    ers_min_attempts: int = 20  # меньше ответов по предмету — «Недостаточно данных»
    ers_mastery_threshold: float = 0.8  # тема освоена — 80%+ по последним попыткам

    # Модуль 4: вход по SMS и семейный аккаунт
    sms_provider: str = "log"  # log — код в лог (разработка) | eskiz — Eskiz.uz
    eskiz_email: str = ""
    eskiz_password: str = ""
    eskiz_from: str = "4546"
    sms_code_ttl: int = 300  # 5 минут
    sms_max_attempts: int = 5
    sms_resend_seconds: int = 60
    sms_hourly_limit: int = 5
    family_max_adults: int = 4
    family_max_children: int = 6
    family_invite_hours: int = 24

    # PWA: Web Push (без Telegram). Ключи — python scripts/gen_vapid.py
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@example.com"
    push_worker: bool = True

    # Ограничение частоты запросов к API с одного IP (в минуту)
    rate_limit_auth: int = 10
    rate_limit_explain: int = 20
    rate_limit_api: int = 180

    # Персональные данные и согласие
    # Демо-режим: ученик занимается без согласия родителя (для показа и локальной проверки)
    demo_mode: bool = False
    # Ученик занимается только после согласия родителя в боте.
    # Не задано — нужно всегда, кроме демо-режима (DEMO_MODE=1 или GEMINI_FAKE=1)
    require_parent_consent: bool | None = None
    privacy_policy_url: str = ""  # пусто — страница /privacy на нашем сайте
    policy_version: str = "2026-09-25"  # сменил текст политики — поменяй версию: нужно новое согласие
    operator_name: str = "[Название организации — оператора персональных данных]"
    operator_contact: str = "[e-mail и телефон для обращений]"
    data_location: str = "[Город, страна дата-центра, где хранятся данные]"

    @field_validator("owner_id", "require_parent_consent", mode="before")
    @classmethod
    def _empty_is_none(cls, value):
        # OWNER_ID= / REQUIRE_PARENT_CONSENT= (пусто) в .env — значит не задано
        return None if value in ("", None) else value

    @property
    def async_database_url(self) -> str:
        """Приводит URL к async-драйверу: asyncpg для PostgreSQL, aiosqlite для SQLite."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql://"):
            return "postgresql+asyncpg://" + url[len("postgresql://") :]
        if url.startswith("sqlite:///"):
            return "sqlite+aiosqlite:///" + url[len("sqlite:///") :]
        return url

    @property
    def parent_consent_required(self) -> bool:
        if self.require_parent_consent is None:
            return not (self.demo_mode or self.gemini_fake)
        return self.require_parent_consent

    @property
    def policy_url(self) -> str:
        return self.privacy_policy_url or self.web_url.rstrip("/") + "/privacy"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def web_app_enabled(self) -> bool:
        """Telegram принимает Mini App и url-кнопки только с HTTPS."""
        return self.web_url.startswith("https://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
