"""Учитель: привязка учеников и статистика класса."""
from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import t
from app.db.models import Student, User
from app.db.session import SessionLocal
from app.repositories.students import (
    completed_count,
    get_teacher_students,
    weak_topics,
)
from app.repositories.users import get_user
from app.services.accounts import AccountError, link_by_family_code
from bot.keyboards import new_code_keyboard, teacher_menu_keyboard

router = Router()


class TeacherStates(StatesGroup):
    waiting_code = State()


async def _student_line(session: AsyncSession, student: Student) -> tuple[str, User]:
    user = await get_user(session, student.user_id)
    weak = await weak_topics(session, student.user_id, limit=3)
    if weak:
        items = ", ".join(f"{escape(title.strip())} — {count} {t('mistakes_short')}" for title, count in weak)
        weak_line = t("class_weak", items=items)
    else:
        weak_line = t("class_no_weak")
    last = student.last_active_on.strftime("%d.%m") if student.last_active_on else "—"
    line = t(
        "class_line",
        name=escape(user.full_name or t("default_student")),
        code=student.family_code,
        last=last,
        topics=await completed_count(session, student.user_id),
    )
    return f"{line}\n{weak_line}", user


async def _class_report(teacher_id: int) -> tuple[str, object] | None:
    async with SessionLocal() as session:
        students = await get_teacher_students(session, teacher_id)
        if not students:
            return None
        lines = [t("class_header")]
        with_login = []
        for student in students:
            line, user = await _student_line(session, student)
            lines.append(line)
            if user.login:
                with_login.append((user.id, user.display_name))
    return "\n".join(lines), new_code_keyboard(with_login)


@router.callback_query(F.data == "teacher:bind")
async def on_bind(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TeacherStates.waiting_code)
    await callback.answer()
    await callback.message.answer(t("ask_teacher_code"))


@router.message(TeacherStates.waiting_code, F.text)
async def on_teacher_code(message: Message, state: FSMContext, user: User) -> None:
    async with SessionLocal() as session:
        try:
            _, created = await link_by_family_code(session, user, message.text, "teacher")
        except AccountError as exc:
            await message.answer(t(exc.code))
            return
    await state.clear()
    await message.answer(
        t("teacher_link_ok" if created else "already_linked"),
        reply_markup=teacher_menu_keyboard(),
    )


@router.message(Command("class"))
async def cmd_class(message: Message, user: User) -> None:
    report = await _class_report(user.id)
    if report is None:
        await message.answer(t("class_empty"))
        return
    await message.answer(report[0], reply_markup=report[1])


@router.callback_query(F.data == "teacher:class")
async def on_class_callback(callback: CallbackQuery, user: User) -> None:
    report = await _class_report(user.id)
    if report is None:
        await callback.answer(t("class_empty"), show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(report[0], reply_markup=report[1])
