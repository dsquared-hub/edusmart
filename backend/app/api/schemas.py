from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TelegramAuthIn(BaseModel):
    """Либо данные Login Widget, либо initData из Mini App."""

    widget: dict | None = None
    init_data: str | None = None
    # Страница входа: student — обычная, teacher — ментора
    as_role: Literal["student", "teacher"] | None = None


class CodeAuthIn(BaseModel):
    login: str = Field(min_length=3, max_length=32)
    code: str = Field(min_length=4, max_length=12)


class BotLoginStartIn(BaseModel):
    as_role: Literal["student", "teacher"] | None = None


class BotLoginPollIn(BaseModel):
    token: str = Field(min_length=16, max_length=64)


class SettingsIn(BaseModel):
    theme: Literal["sun", "ocean", "forest", "berry"] | None = None
    high_contrast: bool | None = None
    dyslexia_font: bool | None = None
    lang: Literal["ru", "uz", "en"] | None = None


class AnswerIn(BaseModel):
    step: int = Field(ge=0)
    option: int = Field(ge=0)


class ReportIn(BaseModel):
    """«⚠️ Здесь ошибка»: шаг объяснения или задача закрепления."""

    step: int = Field(ge=0)
    kind: Literal["step", "practice"] = "step"
    comment: str | None = Field(default=None, max_length=500)
