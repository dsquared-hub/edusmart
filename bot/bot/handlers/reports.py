"""Жалобы «⚠️ Здесь ошибка»: /reports — учителю (по его ученикам) и владельцу (все)."""
from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.core.i18n import t
from app.db.models import ContentReport, User
from app.db.session import SessionLocal
from app.repositories import reports as reports_repo
from app.repositories.students import is_linked_teacher
from app.repositories.topics import get_topic
from app.repositories.users import get_user
from bot.keyboards import resolve_keyboard
from bot.render import describe
from bot.security import SecurityManager

router = Router()


def _is_owner(user: User, security: SecurityManager) -> bool:
    return security.owner_id is not None and user.telegram_id == security.owner_id


@router.message(Command("reports"))
async def cmd_reports(message: Message, user: User, security: SecurityManager) -> None:
    owner = _is_owner(user, security)
    if not owner and user.role != "teacher":
        await message.answer(t("forbidden"))
        return
    async with SessionLocal() as session:
        rows = await reports_repo.recent_reports(
            session, teacher_id=None if owner else user.id, limit=10
        )
        if not rows:
            await message.answer(t("reports_empty"))
            return
        lines = [t("reports_header")]
        for report, topic in rows:
            student = await get_user(session, topic.student_user_id)
            comment = f"\n💬 {escape(report.comment)}" if report.comment else ""
            lines.append(
                t(
                    "reports_line",
                    id=report.id,
                    name=escape(student.display_name if student else "—"),
                    comment=comment,
                    **{k: v for k, v in describe(report, topic).items()},
                )
            )
    await message.answer("\n\n".join(lines), reply_markup=resolve_keyboard([r.id for r, _ in rows]))


@router.callback_query(F.data.startswith("resolve:"))
async def on_resolve(callback: CallbackQuery, user: User, security: SecurityManager) -> None:
    report_id = int(callback.data.split(":", 1)[1])
    async with SessionLocal() as session:
        report = await session.get(ContentReport, report_id)
        topic = await get_topic(session, report.topic_id) if report else None
        allowed = topic is not None and (
            _is_owner(user, security)
            or await is_linked_teacher(session, user.id, topic.student_user_id)
        )
        if not allowed:
            await callback.answer(t("forbidden"), show_alert=True)
            return
        await reports_repo.resolve(session, report_id)
        await session.commit()
    await callback.answer(t("report_resolved", id=report_id), show_alert=True)
