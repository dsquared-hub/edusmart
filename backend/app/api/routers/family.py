"""API Модуля 4: вечерний тест, Exam Readiness Score, отчёт родителю, задания."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_session
from app.db.models import Assignment, CurriculumSubject, CurriculumTopic, User
from app.services import evening, family_report
from app.services import teacher_panel as teacher_panel_svc
from app.services.questions import QuestionGenerator, make_question_generator

router = APIRouter(prefix="/api/v1", tags=["family"])


def get_question_generator(request: Request) -> QuestionGenerator:
    generator = getattr(request.app.state, "questions", None)
    if generator is None:
        generator = request.app.state.questions = make_question_generator()
    return generator


def _raise(exc: evening.EveningError | family_report.ReportError):
    raise HTTPException(exc.status, detail={"code": exc.code})


# ---------- Вечерний тест ----------

@router.get("/evening")
async def evening_status(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    data = await evening.status(session, user)
    if data["test"] and data["test"]["status"] == "active":
        test = await evening.get_test(session, user, data["test"]["id"])
        data["question"] = await evening.question_view(session, test, user)
    return data


@router.post("/evening/start")
async def evening_start(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    generator: QuestionGenerator = Depends(get_question_generator),
):
    try:
        test = await evening.start(session, user, generator)
    except evening.EveningError as exc:
        _raise(exc)
    return {"id": test.id, "question": await evening.question_view(session, test, user)}


class AnswerIn(BaseModel):
    slot: int = Field(ge=0)
    option: int = Field(ge=0)
    time_ms: int = Field(0, ge=0)


@router.post("/evening/{test_id}/answer")
async def evening_answer(
    test_id: int,
    body: AnswerIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    generator: QuestionGenerator = Depends(get_question_generator),
):
    try:
        test, result = await evening.answer(session, user, test_id, body.slot, body.option, body.time_ms, generator)
    except evening.EveningError as exc:
        _raise(exc)
    data = {
        "correct": result.correct,
        "retry": result.retry,
        "explanation": result.explanation,
        "correct_option": result.correct_option,
        "points": result.points,
        "finished": result.finished,
    }
    if result.finished:
        summary = evening.summary(test)
        weak = await session.get(CurriculumTopic, summary["weak_topic_id"]) if summary["weak_topic_id"] else None
        data["summary"] = {**summary, "weak_topic": weak.name(user.lang) if weak else None}
    elif not result.retry:
        data["question"] = await evening.question_view(session, test, user)
    return data


# ---------- ERS, отчёт родителю, задания ----------

@router.get("/readiness")
async def get_readiness(student_id: int | None = None, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    target = student_id or user.id
    try:
        await family_report.ensure_can_view(session, user, target)
    except family_report.ReportError as exc:
        _raise(exc)
    return {"subjects": await family_report.readiness_view(session, target, user.lang)}


@router.get("/family/report")
async def get_report(student_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    try:
        return await family_report.report(session, user, student_id)
    except family_report.ReportError as exc:
        _raise(exc)


class AssignIn(BaseModel):
    student_id: int
    topic_id: int
    note: str | None = Field(None, max_length=500)


@router.post("/assignments")
async def create_assignment(body: AssignIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    try:
        item = await family_report.assign(session, user, body.student_id, body.topic_id, body.note)
    except family_report.ReportError as exc:
        _raise(exc)
    return {"id": item.id}


@router.get("/assignments")
async def my_assignments(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    """Открытые задания ученика (от родителя или учителя)."""
    rows = await session.execute(
        select(Assignment, CurriculumTopic)
        .join(CurriculumTopic, CurriculumTopic.id == Assignment.topic_id)
        .where(Assignment.student_id == user.id, Assignment.done_at.is_(None))
        .order_by(Assignment.created_at.desc())
    )
    return {
        "assignments": [
            {"id": a.id, "topic_id": t.id, "topic": t.name(user.lang), "note": a.note, "created_at": a.created_at.isoformat() + "Z"}
            for a, t in rows.all()
        ]
    }


@router.get("/teacher/panel")
async def teacher_panel(subject_id: int | None = None, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    """Панель учителя: тепловая карта, «кому нужна помощь», частые вопросы класса."""
    try:
        return await teacher_panel_svc.panel(session, user, subject_id)
    except teacher_panel_svc.PanelError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code})


class ClassAssignIn(BaseModel):
    topic_id: int
    student_ids: list[int] | None = None  # не указано — всему классу
    note: str | None = Field(None, max_length=500)


@router.post("/teacher/assignments")
async def teacher_assign(body: ClassAssignIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    try:
        count = await teacher_panel_svc.assign_class(session, user, body.topic_id, body.student_ids, body.note)
    except teacher_panel_svc.PanelError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code})
    return {"assigned": count}


@router.get("/curriculum/topics")
async def curriculum_topics(grade: int | None = None, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    """Темы программы — для выбора темы задания."""
    stmt = select(CurriculumTopic, CurriculumSubject).join(CurriculumSubject)
    if grade:
        stmt = stmt.where(CurriculumTopic.grade == grade)
    rows = await session.execute(stmt.order_by(CurriculumSubject.grade, CurriculumSubject.code, CurriculumTopic.order))
    return {"topics": [{"id": t.id, "name": t.name(user.lang), "subject": s.name_ru if user.lang == "ru" else (s.name_uz if user.lang == "uz" else s.name_en), "grade": t.grade} for t, s in rows.all()]}


class EveningTimeIn(BaseModel):
    student_id: int
    time: str = Field(pattern=r"^\d{2}:\d{2}$")


@router.put("/family/evening-time")
async def put_evening_time(body: EveningTimeIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    try:
        student = await family_report.set_evening_time(session, user, body.student_id, body.time)
    except family_report.ReportError as exc:
        _raise(exc)
    return {"evening_time": student.evening_time}
