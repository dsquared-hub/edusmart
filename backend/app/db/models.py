"""Модели базы данных (SQLAlchemy 2.0). Целевая СУБД — PostgreSQL.

Один пользователь = одна строка users, откуда бы он ни зашёл:
Telegram (бот, Login Widget, Mini App) или логин+код без Telegram.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.timeutil import utcnow

# JSONB в PostgreSQL, обычный JSON в SQLite (тесты)
JSONType = JSON().with_variant(JSONB(), "postgresql")
# SQLite автоинкрементирует только INTEGER PRIMARY KEY
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


ROLES = ("student", "parent", "teacher")
# Одна палитра «Капучино»: sun — светлая, night — тёмная. Старые темы читаются как sun.
THEMES = ("sun", "night")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    username: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str | None] = mapped_column(String(16))

    # Номер (+998…) из «Поделиться номером» в боте — один номер = один пользователь
    phone: Mapped[str | None] = mapped_column(String(16), unique=True)

    # Вход без Telegram: логин + код, который выдал родитель/учитель
    login: Mapped[str | None] = mapped_column(String(32), unique=True)
    access_code_hash: Mapped[str | None] = mapped_column(String(255))
    code_issued_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    # +1 при выходе / новом коде — все выданные ранее токены сайта перестают работать
    token_version: Mapped[int] = mapped_column(Integer, default=0)

    # Оформление сайта — хранится в профиле
    theme: Mapped[str] = mapped_column(String(16), default="sun")
    high_contrast: Mapped[bool] = mapped_column(Boolean, default=False)
    dyslexia_font: Mapped[bool] = mapped_column(Boolean, default=False)
    lang: Mapped[str] = mapped_column(String(5), default="ru")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    @property
    def display_name(self) -> str:
        return self.full_name or self.username or self.login or "друг"


class Student(Base):
    __tablename__ = "students"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    points: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    last_active_on: Mapped[date | None] = mapped_column(Date)
    family_code: Mapped[str] = mapped_column(String(6), unique=True)
    consent_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    # На какую версию политики дано согласие. Новая версия — нужно новое согласие.
    consent_version: Mapped[str | None] = mapped_column(String(32))
    grade: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # Заморозки серии (Модуль 4): 2 бесплатных пропуска в неделю, счётчик — на ISO-неделю
    freeze_week: Mapped[str | None] = mapped_column(String(10))  # «2026-W39»
    freezes_used: Mapped[int] = mapped_column(SmallInteger, default=0)
    # Время напоминания о вечернем тесте — выбирает семья (по Ташкенту)
    evening_time: Mapped[str] = mapped_column(String(5), default="19:00")
    last_reminded_on: Mapped[date | None] = mapped_column(Date)
    # Родителю — одно мягкое напоминание в день, если тест ещё не пройден
    parent_reminded_on: Mapped[date | None] = mapped_column(Date)
    # Дневное уведомление родителю (PARENT_DAY_PUSH, 16:30) — раз в день
    parent_day_pushed_on: Mapped[date | None] = mapped_column(Date)
    # Магазин персонажа: очки обмениваются на коины. Уровень считается по всем
    # заработанным очкам (points), обмен его не снижает — тратится только остаток.
    coins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    points_exchanged: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class ParentLink(Base):
    __tablename__ = "parent_links"
    __table_args__ = (UniqueConstraint("parent_user_id", "student_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    student_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.user_id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class TeacherLink(Base):
    __tablename__ = "teacher_links"
    __table_args__ = (UniqueConstraint("teacher_user_id", "student_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    student_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.user_id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Topic(Base):
    """Одно объяснение темы. Состояние хранится здесь, а не в памяти бота,
    поэтому продолжить можно и на сайте, и в боте с того же шага."""

    __tablename__ = "topics"
    __table_args__ = (Index("ix_topics_student_status", "student_user_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.user_id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str | None] = mapped_column(String(255))
    subject: Mapped[str | None] = mapped_column(String(32))
    grade: Mapped[int | None] = mapped_column(SmallInteger)
    source: Mapped[str] = mapped_column(String(8), default="bot")  # bot | web
    status: Mapped[str] = mapped_column(
        String(16), default="in_progress"
    )  # in_progress | completed | abandoned
    steps: Mapped[list] = mapped_column(JSONType, default=list)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    points_earned: Mapped[int] = mapped_column(Integer, default=0)
    practice: Mapped[list | None] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Тема школьной программы, к которой относится объяснение (для вечернего теста и ERS)
    curriculum_topic_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("curriculum_topics.id", ondelete="SET NULL"), index=True
    )

    @property
    def total_steps(self) -> int:
        return len(self.steps or [])


class StepAttempt(Base):
    __tablename__ = "step_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("topics.id", ondelete="CASCADE"), index=True
    )
    step_index: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DailyUsage(Base):
    """Счётчик объяснений за день — общий для сайта и бота."""

    __tablename__ = "daily_usage"
    __table_args__ = (UniqueConstraint("user_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date)
    explanations: Mapped[int] = mapped_column(Integer, default=0)
    simplifications: Mapped[int] = mapped_column(Integer, default=0)


class ActivityDay(Base):
    __tablename__ = "activity_days"
    __table_args__ = (UniqueConstraint("user_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date)


class BlockedUser(Base):
    """Кому закрыт доступ (бан владельца бота). Действует и в боте, и на сайте.

    Ключ — Telegram ID: заблокировать можно и того, кто ещё не заходил.
    """

    __tablename__ = "blocked_users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ConsentRecord(Base):
    """Журнал согласий: кто, за кого, когда и на какую версию политики.

    Без внешних ключей намеренно: запись — юридическое доказательство и
    остаётся даже после удаления данных ребёнка.
    """

    __tablename__ = "consent_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    parent_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    student_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    policy_version: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(16), default="granted")  # granted | deleted
    channel: Mapped[str] = mapped_column(String(8), default="bot")  # bot | web
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ContentReport(Base):
    """«⚠️ Здесь ошибка» — жалоба ученика/учителя на объяснение или задачу."""

    __tablename__ = "content_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("topics.id", ondelete="CASCADE"), index=True
    )
    step_index: Mapped[int] = mapped_column(Integer, default=0)
    kind: Mapped[str] = mapped_column(String(16), default="step")  # step | practice
    reporter_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    comment: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)  # open | resolved
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SupportTicket(Base):
    """Обращение в поддержку из бота (родитель/учитель) и ответ владельца."""

    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(String(2000))
    has_photo: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)  # open | answered
    reply: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime)


class WorkCheck(Base):
    """Academic Copilot: пакет рукописных работ на ИИ-проверку (Модуль 5.1).

    queued → processing → review → confirmed | failed. ИИ только предлагает оценку:
    в журнал она попадает лишь после подтверждения учителем.
    """

    __tablename__ = "work_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str | None] = mapped_column(String(32))
    grade: Mapped[int | None] = mapped_column(SmallInteger)
    task_text: Mapped[str | None] = mapped_column(String(4000))  # задание
    answer_key: Mapped[str | None] = mapped_column(String(4000))  # ключ ответов
    max_score: Mapped[int] = mapped_column(SmallInteger, default=5)
    # Правки учителя можно использовать для дообучения — только с согласия школы
    training_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)


class WorkCheckItem(Base):
    """Одна работа (файл) внутри проверки: результат ИИ и решение учителя — раздельно,
    чтобы правки учителя оставались размеченными данными."""

    __tablename__ = "work_check_items"
    __table_args__ = (Index("ix_work_check_items_status_created", "status", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    check_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("work_checks.id", ondelete="CASCADE"), index=True
    )
    student_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("students.user_id", ondelete="SET NULL"), index=True
    )
    file_name: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(128))  # имя файла в MEDIA_DIR
    status: Mapped[str] = mapped_column(String(16), default="queued")
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    error: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Предложение ИИ
    recognized_text: Mapped[str | None] = mapped_column(String(8000))
    ai_score: Mapped[int | None] = mapped_column(SmallInteger)
    ai_comment: Mapped[str | None] = mapped_column(String(2000))
    ai_marks: Mapped[list | None] = mapped_column(JSONType)
    confidence: Mapped[int | None] = mapped_column(SmallInteger)  # 0–100
    neatness: Mapped[int | None] = mapped_column(SmallInteger)  # аккуратность оформления 0–100

    # Решение учителя (итог всегда за ним)
    teacher_score: Mapped[int | None] = mapped_column(SmallInteger)
    teacher_comment: Mapped[str | None] = mapped_column(String(2000))
    teacher_marks: Mapped[list | None] = mapped_column(JSONType)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime)  # учитель открыл работу
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    @property
    def final_score(self) -> int | None:
        return self.teacher_score if self.teacher_score is not None else self.ai_score


class Textbook(Base):
    """Учебник для генерации уроков (Модуль 5.2): библиотека платформы (owner = NULL)
    или PDF, загруженный учителем для своих уроков."""

    __tablename__ = "textbooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_teacher_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str | None] = mapped_column(String(32))
    grade: Mapped[int | None] = mapped_column(SmallInteger)
    # Права на контент: на каком основании учебник загружен в ИИ
    license_note: Mapped[str | None] = mapped_column(String(500))
    pages: Mapped[int] = mapped_column(Integer, default=0)
    embed_model: Mapped[str | None] = mapped_column(String(64))  # эмбеддинги какого поставщика
    status: Mapped[str] = mapped_column(String(16), default="processing")  # processing | ready | failed
    error: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class TextbookChunk(Base):
    """Фрагмент учебника с номером страницы и эмбеддингом — основа RAG."""

    __tablename__ = "textbook_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    textbook_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("textbooks.id", ondelete="CASCADE"), index=True
    )
    page: Mapped[int] = mapped_column(Integer)
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(String(4000))
    # JSON-массив чисел. В PostgreSQL следующий шаг — колонка pgvector и индекс HNSW
    embedding: Mapped[list] = mapped_column(JSONType)


class LessonMaterial(Base):
    """Сгенерированные и отредактированные учителем материалы урока."""

    __tablename__ = "lesson_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    textbook_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("textbooks.id", ondelete="SET NULL")
    )
    topic: Mapped[str] = mapped_column(String(255))
    lang: Mapped[str] = mapped_column(String(5), default="ru")
    content: Mapped[dict] = mapped_column(JSONType)  # plan, stories, test, answer_key
    sources: Mapped[list] = mapped_column(JSONType)  # страницы учебника
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


# ---------- Модуль 4: программа, вечерний тест, Exam Readiness Score ----------

class CurriculumSubject(Base):
    """Предмет школьной программы для конкретного класса."""

    __tablename__ = "curriculum_subjects"
    __table_args__ = (UniqueConstraint("code", "grade"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32))  # math, physics, … (как в объяснениях)
    grade: Mapped[int] = mapped_column(SmallInteger)
    name_uz: Mapped[str] = mapped_column(String(120))
    name_ru: Mapped[str] = mapped_column(String(120))
    name_en: Mapped[str] = mapped_column(String(120))


class CurriculumTopic(Base):
    """Тема программы. Объяснения и ответы привязываются к ней — так считается освоение."""

    __tablename__ = "curriculum_topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("curriculum_subjects.id", ondelete="CASCADE"), index=True
    )
    grade: Mapped[int] = mapped_column(SmallInteger)
    order: Mapped[int] = mapped_column(Integer, default=0)
    name_uz: Mapped[str] = mapped_column(String(255))
    name_ru: Mapped[str] = mapped_column(String(255))
    name_en: Mapped[str] = mapped_column(String(255))

    def name(self, lang: str) -> str:
        return {"uz": self.name_uz, "en": self.name_en}.get(lang, self.name_ru)


class BankQuestion(Base):
    """Банк вопросов по теме и сложности (1–3). Генерируется ИИ один раз и
    переиспользуется всеми учениками — кэш ради лимита расходов на ИИ."""

    __tablename__ = "question_bank"
    __table_args__ = (Index("ix_question_bank_topic_difficulty", "topic_id", "difficulty", "lang"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("curriculum_topics.id", ondelete="CASCADE")
    )
    difficulty: Mapped[int] = mapped_column(SmallInteger)
    lang: Mapped[str] = mapped_column(String(5))
    question: Mapped[str] = mapped_column(String(1000))
    options: Mapped[list] = mapped_column(JSONType)
    correct: Mapped[int] = mapped_column(SmallInteger)
    explanation: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Attempt(Base):
    """Ответ ученика на вопрос по теме программы (вечерний тест и др.)."""

    __tablename__ = "attempts"
    __table_args__ = (
        Index("ix_attempts_student_topic", "student_id", "topic_id"),
        Index("ix_attempts_student_created", "student_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.user_id", ondelete="CASCADE")
    )
    topic_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("curriculum_topics.id", ondelete="CASCADE")
    )
    question_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("question_bank.id", ondelete="SET NULL")
    )
    is_correct: Mapped[bool] = mapped_column(Boolean)
    time_ms: Mapped[int] = mapped_column(Integer, default=0)
    is_review: Mapped[bool] = mapped_column(Boolean, default=False)  # интервальное повторение
    source: Mapped[str] = mapped_column(String(16), default="evening")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DailyTest(Base):
    """Вечерний тест: один в день (по Ташкенту). Вопросы подбираются по ходу —
    сложность меняется от ответа к ответу."""

    __tablename__ = "daily_tests"
    __table_args__ = (UniqueConstraint("student_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.user_id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | finished
    topic_ids: Mapped[list] = mapped_column(JSONType)
    slots: Mapped[list] = mapped_column(JSONType)  # [{topic_id, review, question_id, result}]
    current: Mapped[int] = mapped_column(SmallInteger, default=0)
    difficulty: Mapped[int] = mapped_column(SmallInteger, default=2)
    retry: Mapped[bool] = mapped_column(Boolean, default=False)  # ждём исправления после ошибки
    score: Mapped[int] = mapped_column(SmallInteger, default=0)  # верно с первой попытки
    corrected: Mapped[int] = mapped_column(SmallInteger, default=0)  # исправлено после объяснения
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class ReadinessScore(Base):
    """История Exam Readiness Score по предмету (для графика динамики)."""

    __tablename__ = "readiness_scores"
    __table_args__ = (Index("ix_readiness_student_subject", "student_id", "subject_id", "calculated_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.user_id", ondelete="CASCADE")
    )
    subject_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("curriculum_subjects.id", ondelete="CASCADE")
    )
    score: Mapped[int | None] = mapped_column(SmallInteger)  # None — недостаточно данных
    components: Mapped[dict] = mapped_column(JSONType)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Assignment(Base):
    """Задание ученику по теме — от родителя («Прислать ребёнку задание») или учителя."""

    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.user_id", ondelete="CASCADE"), index=True
    )
    topic_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("curriculum_topics.id", ondelete="CASCADE")
    )
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    done_at: Mapped[datetime | None] = mapped_column(DateTime)


# ---------- Модуль 4: семейный аккаунт ----------

class Family(Base):
    """Семья: у ребёнка может быть несколько взрослых, у взрослого — несколько детей."""

    __tablename__ = "families"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class FamilyMember(Base):
    __tablename__ = "family_members"
    __table_args__ = (UniqueConstraint("family_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    family_id: Mapped[int] = mapped_column(Integer, ForeignKey("families.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    member_role: Mapped[str] = mapped_column(String(16))  # student | parent | guardian
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class FamilyInvite(Base):
    """Приглашение в семью: 6-значный код или QR, живёт 24 часа, срабатывает один раз."""

    __tablename__ = "family_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    family_id: Mapped[int] = mapped_column(Integer, ForeignKey("families.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(6), unique=True)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    used_at: Mapped[datetime | None] = mapped_column(DateTime)


class PushSubscription(Base):
    """Web Push-подписка браузера или установленного PWA (без Telegram)."""

    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    endpoint: Mapped[str] = mapped_column(String(1000), unique=True)
    p256dh: Mapped[str] = mapped_column(String(200))
    auth: Mapped[str] = mapped_column(String(100))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime)


class Event(Base):
    """Очередь событий (outbox): сайт пишет, бот и web push доставляют уведомления.

    Каналы независимы: processed_at — отметка бота (Telegram), pushed_at — Web Push."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)


class StudentItem(Base):
    """Вещь персонажа, купленная учеником за коины (каталог — в services/avatar.py)."""

    __tablename__ = "student_items"
    __table_args__ = (UniqueConstraint("user_id", "item_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.user_id", ondelete="CASCADE"), index=True
    )
    item_code: Mapped[str] = mapped_column(String(32))
    equipped: Mapped[bool] = mapped_column(Boolean, default=False)
    bought_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ---------- Stories для ученика (микро-обучение) ----------

class StoryDeck(Base):
    """Stories-урок: короткие карточки по теме и мини-вопросы между ними.

    Делает сам ученик (ИИ по его теме) или учитель отправляет Stories из материалов
    урока по учебнику (material_id) — тогда колода общая для его учеников.
    slides: [{"emoji", "title", "text", "question"?, "options"?, "correct"?, "explanation"?}]
    """

    __tablename__ = "story_decks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    author_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    material_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("lesson_materials.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str | None] = mapped_column(String(32))
    lang: Mapped[str] = mapped_column(String(5), default="ru")
    slides: Mapped[list] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class StoryView(Base):
    """Stories в ленте ученика: прогресс, ответы с первой попытки и выданные EduCoin."""

    __tablename__ = "story_views"
    __table_args__ = (UniqueConstraint("deck_id", "student_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deck_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("story_decks.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.user_id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(8), default="new")  # new | done
    answers: Mapped[dict] = mapped_column(JSONType, default=dict)  # {"<слайд>": верно с первой попытки}
    coins: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


# ---------- Сократовский тьютор ----------

class TutorSession(Base):
    """Диалог с сократовским репетитором: ИИ ведёт наводящими вопросами, ответ ученик
    находит сам. messages: [{"role": "student"|"tutor", "text", "at"}]. Фото задачи не
    храним — только условие своими словами (problem), которое модель написала на 1-м ходу."""

    __tablename__ = "tutor_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.user_id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    problem: Mapped[str] = mapped_column(Text, default="")
    subject: Mapped[str | None] = mapped_column(String(32))
    grade: Mapped[int | None] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(String(8), default="active")  # active | solved
    messages: Mapped[list] = mapped_column(JSONType, default=list)
    points: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


# ---------- Квесты Paper-to-Digital ----------

class PaperQuest(Base):
    """Квест «реши в тетради»: задача из закрепления пройденной темы, ученик решает на бумаге
    и фотографирует. Vision-модель проверяет решение и почерк; верно — EduCoin ×2.
    Фото не храним — только итог проверки."""

    __tablename__ = "paper_quests"
    __table_args__ = (UniqueConstraint("student_id", "topic_id", "task_index"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.user_id", ondelete="CASCADE"), index=True
    )
    topic_id: Mapped[int] = mapped_column(Integer, ForeignKey("topics.id", ondelete="CASCADE"))
    task_index: Mapped[int] = mapped_column(SmallInteger)
    task: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(String(255))  # ключ — ученику не показываем до сдачи
    status: Mapped[str] = mapped_column(String(8), default="open")  # open | passed
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    score: Mapped[int | None] = mapped_column(SmallInteger)
    neatness: Mapped[int | None] = mapped_column(SmallInteger)
    comment: Mapped[str | None] = mapped_column(Text)
    coins: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    passed_at: Mapped[datetime | None] = mapped_column(DateTime)


# ---------- ДТМ-симулятор ----------

class DtmQuestion(Base):
    """Банк вопросов тренировочного ДТМ: генерируется ИИ по разделам предмета, каждый ответ
    перепроверен вторым запросом, переиспользуется всеми учениками."""

    __tablename__ = "dtm_questions"
    __table_args__ = (Index("ix_dtm_questions_subject_lang", "subject", "lang"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String(32))
    section: Mapped[str] = mapped_column(String(255))
    lang: Mapped[str] = mapped_column(String(5))
    question: Mapped[str] = mapped_column(String(1000))
    options: Mapped[list] = mapped_column(JSONType)
    correct: Mapped[int] = mapped_column(SmallInteger)
    explanation: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DtmTest(Base):
    """Вариант ДТМ ученика: 3 обязательных блока по 10 вопросов и 2 профильных по 30,
    180 минут. slots: [{"block", "subject", "question_id", "answer": int | None}].
    Время — по серверу (deadline_at); после него ответы не принимаются."""

    __tablename__ = "dtm_tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.user_id", ondelete="CASCADE"), index=True
    )
    spec1: Mapped[str] = mapped_column(String(32))
    spec2: Mapped[str] = mapped_column(String(32))
    lang: Mapped[str] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(8), default="active")  # active | finished
    slots: Mapped[list] = mapped_column(JSONType)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    deadline_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    score: Mapped[float | None] = mapped_column(Float)
    results: Mapped[dict | None] = mapped_column(JSONType)  # по блокам: верно, баллы


# ---------- IELTS AI Coach ----------

class IeltsMaterial(Base):
    """Задание IELTS, сгенерированное ИИ и проверенное (writing1 — с данными графика,
    writing2, reading, listening, speaking). Общее для всех учеников — переиспользуется."""

    __tablename__ = "ielts_materials"
    __table_args__ = (Index("ix_ielts_materials_kind", "kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16))
    content: Mapped[dict] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class IeltsAttempt(Base):
    """Попытка ученика по секции IELTS: ответы (эссе / ответы теста / реплики Speaking),
    итог проверки и Band Score (0–9 с шагом 0.5; None — ещё не проверено)."""

    __tablename__ = "ielts_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.user_id", ondelete="CASCADE"), index=True
    )
    material_id: Mapped[int] = mapped_column(Integer, ForeignKey("ielts_materials.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(8), default="active")  # active | done
    answers: Mapped[dict] = mapped_column(JSONType, default=dict)
    result: Mapped[dict | None] = mapped_column(JSONType)
    band: Mapped[float | None] = mapped_column(Float)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


# ---------- PvP-дуэли ----------

class Duel(Base):
    """Асинхронная дуэль двух учеников: одни и те же 5 вопросов, время ответа засекает сервер.
    code — приглашение для друга (НЕ семейный код: тот даёт родителю доступ к ребёнку).
    questions: [{"question", "options", "correct", "explanation"}];
    results: {"<user_id>": {"answers": [{"option", "ok", "ms"}], "shown_at": iso | None, "done": bool}}."""

    __tablename__ = "duels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(8), unique=True)
    creator_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.user_id", ondelete="CASCADE"), index=True
    )
    opponent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("students.user_id", ondelete="CASCADE"), index=True
    )
    topic: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str | None] = mapped_column(String(32))
    grade: Mapped[int | None] = mapped_column(SmallInteger)
    lang: Mapped[str] = mapped_column(String(5))
    public: Mapped[bool] = mapped_column(Boolean, default=False)  # открытый вызов — для случайного соперника
    status: Mapped[str] = mapped_column(String(8), default="open")  # open | active | finished
    questions: Mapped[list] = mapped_column(JSONType)
    results: Mapped[dict] = mapped_column(JSONType, default=dict)
    winner_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
