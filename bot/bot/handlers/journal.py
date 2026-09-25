"""Журнал результатов: /journal и кнопка «📒 Журнал» — для родителя и учителя."""
from __future__ import annotations

from datetime import timezone
from html import escape
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.core.config import get_settings
from app.core.i18n import t
from app.db.models import User
from app.db.session import SessionLocal
from app.services.journal import Journal, JournalError, build_journal
from bot.keyboards import journal_keyboard

router = Router()

RECENT = 10
MAX_STUDENT_LINES = 15
# Лимит Telegram — 4096 символов; оставляем запас на разметку
MAX_TEXT = 3900


def _student_block(s) -> str:
    return t(
        "journal_student",
        name=escape(s.name),
        grade=t("journal_grade", grade=s.grade) if s.grade else "",
        topics=s.topics_completed,
        week=s.topics_week,
        accuracy=f"{s.accuracy}%" if s.accuracy is not None else "—",
    )


def _entry_block(e, tz: ZoneInfo, show_name: bool) -> str:
    when = e.completed_at.replace(tzinfo=timezone.utc).astimezone(tz).strftime("%d.%m %H:%M")
    return t(
        "journal_entry",
        when=when,
        name=f" · {escape(e.student_name)}" if show_name else "",
        title=escape(e.title),
        first_try=e.first_try,
        questions=e.questions,
        mistakes=e.mistakes,
        points=e.points,
        where=t("where_site") if e.source == "web" else "",
    )


def render_journal(journal: Journal) -> str:
    tz = ZoneInfo(get_settings().timezone)
    blocks = [t("journal_header")]
    students = journal.students[:MAX_STUDENT_LINES]
    blocks += [_student_block(s) for s in students]
    if len(journal.students) > len(students):
        blocks.append(t("journal_more_students", n=len(journal.students) - len(students)))

    if not journal.entries:
        blocks.append(t("journal_no_entries"))
        return "\n\n".join(blocks)

    blocks.append(t("journal_recent"))
    show_name = len(journal.students) > 1
    text = "\n\n".join(blocks)
    for entry in journal.entries:
        block = _entry_block(entry, tz, show_name)
        if len(text) + len(block) + 2 > MAX_TEXT:
            break
        text += "\n\n" + block
    return text


async def _journal_reply(user: User, student_id: int | None) -> tuple[str, object]:
    async with SessionLocal() as session:
        try:
            journal = await build_journal(
                session, user, student_id=student_id, limit=RECENT, with_weak=False
            )
        except JournalError as exc:
            key = "journal_forbidden" if exc.code == "not_parent_or_teacher" else "forbidden"
            return t(key), None
    if not journal.students and student_id is None:
        return t("class_empty" if user.role == "teacher" else "profile_parent_empty"), None
    # Кнопки выбора ученика — только в общем журнале и если учеников больше одного
    choices = (
        [(s.id, s.name) for s in journal.students]
        if student_id is None and len(journal.students) > 1
        else []
    )
    return render_journal(journal), journal_keyboard(choices, back=student_id is not None)


@router.message(Command("journal"))
async def cmd_journal(message: Message, user: User) -> None:
    text, kb = await _journal_reply(user, None)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("journal:"))
async def on_journal(callback: CallbackQuery, user: User) -> None:
    arg = callback.data.split(":", 1)[1]
    student_id = int(arg) if arg.isdigit() else None
    text, kb = await _journal_reply(user, student_id)
    await callback.answer()
    await callback.message.answer(text, reply_markup=kb)
