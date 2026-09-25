"""Жалобы «⚠️ Здесь ошибка» на объяснения и задачи."""
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ContentReport, TeacherLink, Topic


async def create_report(
    session: AsyncSession,
    *,
    topic_id: int,
    step_index: int,
    kind: str,
    reporter_user_id: int,
    comment: str | None,
) -> ContentReport:
    report = ContentReport(
        topic_id=topic_id,
        step_index=step_index,
        kind=kind,
        reporter_user_id=reporter_user_id,
        comment=comment,
        status="open",
    )
    session.add(report)
    await session.flush()
    return report


async def already_reported(
    session: AsyncSession, topic_id: int, step_index: int, kind: str, reporter_user_id: int
) -> bool:
    return await session.scalar(
        select(ContentReport.id).where(
            ContentReport.topic_id == topic_id,
            ContentReport.step_index == step_index,
            ContentReport.kind == kind,
            ContentReport.reporter_user_id == reporter_user_id,
        )
    ) is not None


async def recent_reports(
    session: AsyncSession, *, teacher_id: int | None = None, limit: int = 10
) -> list[tuple[ContentReport, Topic]]:
    """Последние открытые жалобы: все (владелец) или по ученикам учителя."""
    stmt = (
        select(ContentReport, Topic)
        .join(Topic, Topic.id == ContentReport.topic_id)
        .where(ContentReport.status == "open")
        .order_by(desc(ContentReport.created_at))
        .limit(limit)
    )
    if teacher_id is not None:
        stmt = stmt.join(TeacherLink, TeacherLink.student_user_id == Topic.student_user_id).where(
            TeacherLink.teacher_user_id == teacher_id
        )
    return [(r, t) for r, t in (await session.execute(stmt)).all()]


async def resolve(session: AsyncSession, report_id: int) -> bool:
    report = await session.get(ContentReport, report_id)
    if report is None or report.status != "open":
        return False
    report.status = "resolved"
    return True
