"""Ученик: «Не понял тему». Вся логика — в общем ExplainService из /backend.

Урок в боте: сначала объяснение всей темы → «Понятно, к вопросам» → вопросы
по одному → после каждого ответа разбор выбранного варианта → следующий вопрос.
"""
from __future__ import annotations

import io
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ContentType
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.core.config import get_settings
from app.core.i18n import t
from app.db.models import Topic, User
from app.db.session import SessionLocal
from app.repositories.topics import list_in_progress
from app.services.explain import (
    MAX_TITLE_LENGTH,
    ExplainError,
    ExplainService,
    StaleStep,
    TopicClosed,
)
from app.services.gamification import level_for
from bot.handlers.common import error_text, safe_edit
from bot.keyboards import (
    completed_keyboard,
    lesson_keyboard,
    resume_keyboard,
    review_keyboard,
    step_keyboard,
)
from bot.render import lesson_messages, question_text, review_text

router = Router()


def _lessons_enabled(_event) -> bool:
    """Дети учатся в приложении; уроки в боте — только в старом режиме BOT_STUDENT_LESSONS=1."""
    return get_settings().bot_student_lessons


router.message.filter(_lessons_enabled)
router.callback_query.filter(_lessons_enabled)


class StudentStates(StatesGroup):
    waiting_topic = State()


async def download_photo(bot: Bot, photo) -> bytes:
    """Скачиваем фото во временный буфер в памяти — нигде не хранится."""
    file = await bot.get_file(photo[-1].file_id)
    buf = io.BytesIO()
    await bot.download_file(file.file_path, buf)
    return buf.getvalue()


async def send_lesson(message: Message, topic: Topic) -> None:
    """Объяснение всей темы; кнопка «к вопросам» — под последней частью."""
    parts = lesson_messages(topic)
    for i, text in enumerate(parts):
        last = i == len(parts) - 1
        markup = lesson_keyboard(topic.id) if last and topic.status == "in_progress" else None
        await message.answer(text, reply_markup=markup)


async def send_step(message: Message, topic: Topic) -> None:
    """Текущий вопрос с вариантами ответа."""
    index = topic.current_step
    step = topic.steps[index]
    await message.answer(
        question_text(step, index, topic.total_steps),
        reply_markup=step_keyboard(topic.id, index, step["options"]),
    )


async def drop_keyboard(message: Message) -> None:
    """Убираем нажатую кнопку, чтобы повторное нажатие не прислало вопрос дважды."""
    try:
        await message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass


def _topic_id(data: str) -> int | None:
    try:
        return int(data.split(":", 1)[1])
    except (IndexError, ValueError):
        return None


@router.callback_query(F.data == "student:help")
async def on_help(
    callback: CallbackQuery, state: FSMContext, user: User, explain: ExplainService
) -> None:
    async with SessionLocal() as session:
        try:
            await explain.ensure_can_start(session, user.id)
        except ExplainError as exc:
            await callback.answer()
            await callback.message.answer(error_text(exc.code, explain))
            return
        resume = await list_in_progress(session, user.id, limit=1)
    await state.set_state(StudentStates.waiting_topic)
    await callback.answer()
    await safe_edit(
        callback.message,
        t("ask_topic"),
        reply_markup=resume_keyboard(resume[0]) if resume else None,
    )


@router.message(
    StudentStates.waiting_topic,
    F.content_type.in_({ContentType.TEXT, ContentType.PHOTO}),
)
async def on_topic_input(
    message: Message, state: FSMContext, bot: Bot, user: User, explain: ExplainService
) -> None:
    title = (message.caption or message.text or "").strip()
    if not message.photo and not title:
        await message.answer(t("ask_topic"))
        return
    if len(title) > MAX_TITLE_LENGTH:
        await message.answer(t("topic_too_long"))
        return

    async with SessionLocal() as session:
        try:
            await explain.ensure_can_start(session, user.id)
        except ExplainError as exc:
            await state.clear()
            await message.answer(error_text(exc.code, explain))
            return

    photo = await download_photo(bot, message.photo) if message.photo else None
    await state.clear()
    await message.answer(t("thinking"))

    async with SessionLocal() as session:
        try:
            topic = await explain.start(
                session,
                user.id,
                title or t("photo_title"),
                photo=photo,
                photo_mime="image/jpeg",
                source="bot",
                lang=user.lang,
            )
        except ExplainError as exc:
            await message.answer(error_text(exc.code, explain))
            return
    await send_lesson(message, topic)


@router.message(StudentStates.waiting_topic)
async def on_wrong_content(message: Message) -> None:
    await message.answer(t("need_text_or_photo"))


@router.callback_query(F.data.startswith("resume:"))
async def on_resume(
    callback: CallbackQuery, state: FSMContext, user: User, explain: ExplainService
) -> None:
    await state.clear()
    topic = await _open_topic(callback, user, explain)
    if topic is None:
        return
    await callback.answer()
    # Ещё не ответил ни на один вопрос — начинаем с объяснения, иначе продолжаем вопросы
    if topic.current_step == 0:
        await send_lesson(callback.message, topic)
    else:
        await send_step(callback.message, topic)


async def _open_topic(
    callback: CallbackQuery, user: User, explain: ExplainService
) -> Topic | None:
    """Тема ученика из callback_data, если она ещё не закрыта (иначе — всплывашка)."""
    topic_id = _topic_id(callback.data)
    if topic_id is None:
        await callback.answer()
        return None
    async with SessionLocal() as session:
        try:
            topic = await explain.get_owned(session, user.id, topic_id)
        except ExplainError as exc:
            await callback.answer(error_text(exc.code, explain), show_alert=True)
            return None
    if topic.status != "in_progress":
        await callback.answer(t("topic_closed"), show_alert=True)
        return None
    return topic


@router.callback_query(F.data.startswith("quiz:"))
async def on_next_question(callback: CallbackQuery, user: User, explain: ExplainService) -> None:
    """«Понятно, к вопросам» и «Следующий вопрос»."""
    topic = await _open_topic(callback, user, explain)
    if topic is None:
        return
    await callback.answer()
    await drop_keyboard(callback.message)
    await send_step(callback.message, topic)


@router.callback_query(F.data.startswith("lesson:"))
async def on_reread(callback: CallbackQuery, user: User, explain: ExplainService) -> None:
    """«Перечитать объяснение» под вопросом."""
    topic = await _open_topic(callback, user, explain)
    if topic is None:
        return
    await callback.answer()
    await drop_keyboard(callback.message)
    await send_lesson(callback.message, topic)


@router.callback_query(F.data.startswith("pause:"))
async def on_pause(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer(t("cancel_done"))
    await safe_edit(callback.message, t("cancel_done"))


@router.callback_query(F.data.startswith("ans:"))
async def on_answer(callback: CallbackQuery, user: User, explain: ExplainService) -> None:
    try:
        _, topic_raw, step_raw, option_raw = callback.data.split(":")
        topic_id, step_index, option = int(topic_raw), int(step_raw), int(option_raw)
    except ValueError:
        await callback.answer()
        return

    async with SessionLocal() as session:
        try:
            result = await explain.answer(
                session, user.id, topic_id, step_index, option, advance_on_wrong=True
            )
        except StaleStep as exc:
            await callback.answer()
            await callback.message.answer(t("stale_step"))
            await send_step(callback.message, exc.topic)
            return
        except TopicClosed:
            await callback.answer(t("topic_closed"), show_alert=True)
            return
        except ExplainError as exc:
            await callback.answer(error_text(exc.code, explain), show_alert=True)
            return

    topic = result.topic
    step = topic.steps[step_index]
    if not result.correct:
        verdict = t("review_wrong")
    elif result.points_awarded:
        verdict = t("correct_short", points=result.points_awarded)
    else:
        verdict = t("correct_no_points")
    await callback.answer(verdict)
    # Разбор выбранного варианта на месте вопроса
    await safe_edit(
        callback.message,
        review_text(step, step_index, topic.total_steps, option, verdict),
        reply_markup=None if result.completed else review_keyboard(topic_id, step_index),
    )

    if result.completed:
        await callback.message.answer(
            t(
                "topic_completed",
                title=escape(topic.title or ""),
                earned=topic.points_earned,
                points=result.total_points,
                level=level_for(result.total_points),
                streak=result.streak,
            ),
            reply_markup=completed_keyboard(topic.id),
        )


@router.callback_query(F.data.startswith("rep:"))
async def on_report(callback: CallbackQuery, user: User, explain: ExplainService) -> None:
    """«⚠️ Здесь ошибка» у шага объяснения."""
    try:
        _, topic_raw, step_raw = callback.data.split(":")
        topic_id, step_index = int(topic_raw), int(step_raw)
    except ValueError:
        await callback.answer()
        return
    async with SessionLocal() as session:
        try:
            created = await explain.report(session, user.id, topic_id, step_index)
        except ExplainError as exc:
            await callback.answer(error_text(exc.code, explain), show_alert=True)
            return
    await callback.answer(t("report_thanks" if created else "report_already"), show_alert=True)
