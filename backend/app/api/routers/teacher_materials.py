"""API Academic Copilot (Модуль 5.2): учебники и генерация материалов урока."""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_session
from app.core.config import get_settings
from app.db.models import LessonMaterial, Textbook, User
from app.services import materials as svc
from app.services.gemini import SUBJECTS
from app.services.media import sniff_mime
from app.services.rag import ingest

router = APIRouter(prefix="/api/v1/teacher", tags=["teacher-materials"])


def _raise(exc: svc.MaterialError):
    raise HTTPException(exc.status, detail={"code": exc.code})


def _iso(value: datetime | None) -> str | None:
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def _book(b: Textbook) -> dict:
    return {
        "id": b.id,
        "title": b.title,
        "subject": b.subject,
        "grade": b.grade,
        "pages": b.pages,
        "status": b.status,
        "error": b.error,
        "library": b.owner_teacher_id is None,
        "created_at": _iso(b.created_at),
    }


def _material(m: LessonMaterial, full: bool = True) -> dict:
    data = {
        "id": m.id,
        "topic": m.topic,
        "textbook_id": m.textbook_id,
        "lang": m.lang,
        "sources": m.sources,
        "created_at": _iso(m.created_at),
        "updated_at": _iso(m.updated_at),
    }
    if full:
        data["content"] = m.content
    return data


@router.get("/textbooks")
async def list_textbooks(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    try:
        return {"textbooks": [_book(b) for b in await svc.list_textbooks(session, user)]}
    except svc.MaterialError as exc:
        _raise(exc)


@router.post("/textbooks")
async def upload_textbook(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(..., min_length=1, max_length=255),
    subject: str | None = Form(None),
    grade: int | None = Form(None, ge=5, le=11),
    # Права на контент (ТЗ, раздел 5): учитель подтверждает основание загрузки
    license_note: str = Form(..., min_length=3, max_length=500),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    settings = get_settings()
    if subject is not None and subject not in SUBJECTS:
        raise HTTPException(422, detail={"code": "bad_subject"})
    limit = settings.textbook_max_mb * 1024 * 1024
    data = await file.read(limit + 1)
    await file.close()
    if len(data) > limit:
        raise HTTPException(413, detail={"code": "file_too_large", "limit_mb": settings.textbook_max_mb})
    if sniff_mime(data) != "application/pdf":
        raise HTTPException(415, detail={"code": "need_pdf"})
    try:
        book = await svc.create_textbook(session, user, title=title, subject=subject, grade=grade, license_note=license_note)
    except svc.MaterialError as exc:
        _raise(exc)
    # Индексация (разбор, фрагменты, эмбеддинги) — в фоне после ответа
    background.add_task(ingest, book.id, data)
    return _book(book)


@router.get("/textbooks/{textbook_id}")
async def get_textbook(textbook_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    try:
        return _book(await svc.textbook_for(session, user, textbook_id))
    except svc.MaterialError as exc:
        _raise(exc)


@router.delete("/textbooks/{textbook_id}")
async def delete_textbook(textbook_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    try:
        await svc.delete_textbook(session, user, textbook_id)
    except svc.MaterialError as exc:
        _raise(exc)
    return {"ok": True}


class GenerateIn(BaseModel):
    textbook_id: int
    topic: str = Field(min_length=1, max_length=255)
    variants: int = Field(2, ge=2, le=4)
    lang: str | None = Field(None, pattern="^(ru|uz|en)$")


@router.post("/materials")
async def generate(body: GenerateIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    try:
        material = await svc.generate_material(
            session, user, textbook_id=body.textbook_id, topic=body.topic, variants=body.variants, lang=body.lang
        )
    except svc.MaterialError as exc:
        _raise(exc)
    return _material(material)


@router.get("/materials")
async def list_materials(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    try:
        return {"materials": [_material(m, full=False) for m in await svc.list_materials(session, user)]}
    except svc.MaterialError as exc:
        _raise(exc)


@router.get("/materials/{material_id}")
async def get_material(material_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    try:
        return _material(await svc.material_for(session, user, material_id))
    except svc.MaterialError as exc:
        _raise(exc)


class MaterialIn(BaseModel):
    content: dict
    topic: str | None = Field(None, max_length=255)


@router.put("/materials/{material_id}")
async def update_material(
    material_id: int, body: MaterialIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    try:
        return _material(await svc.update_material(session, user, material_id, body.content, body.topic))
    except svc.MaterialError as exc:
        _raise(exc)


@router.delete("/materials/{material_id}")
async def delete_material(material_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    try:
        await svc.delete_material(session, user, material_id)
    except svc.MaterialError as exc:
        _raise(exc)
    return {"ok": True}


@router.get("/materials/{material_id}/export.docx")
async def export_docx(material_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    try:
        material = await svc.material_for(session, user, material_id)
    except svc.MaterialError as exc:
        _raise(exc)
    book = await session.get(Textbook, material.textbook_id) if material.textbook_id else None
    data = svc.export_docx(material, book.title if book else None)
    filename = f"{material.topic[:60]}.docx"
    return Response(
        data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
