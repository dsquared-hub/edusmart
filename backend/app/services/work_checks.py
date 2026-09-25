"""Academic Copilot, Модуль 5.1: ИИ-проверка рукописных работ.

Жизненный цикл пакета: queued → processing → review → confirmed | failed.
Очередь — в БД (как очередь уведомлений events): в PostgreSQL обработчики
забирают работы через FOR UPDATE SKIP LOCKED, поэтому их можно запускать
несколько. Сбойная работа повторяется до CHECK_MAX_ATTEMPTS раз.

«ИИ — помощник, а не судья»: оценка попадает к ученику и родителю только после
подтверждения учителем, а правила подтверждения зависят от уверенности ИИ.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.timeutil import utcnow
from app.db.models import User, WorkCheck, WorkCheckItem
from app.db.session import SessionLocal, is_postgres
from app.repositories import events as events_repo
from app.repositories.students import is_linked_teacher
from app.services import media
from app.services.vision import CheckTask, WorkChecker, validate_result

log = logging.getLogger(__name__)

EVENT_CHECK_READY = "check_ready"  # пакет проверен ИИ — учителю в бот
EVENT_WORK_GRADED = "work_graded"  # учитель подтвердил оценку — родителям в бот

ACTIVE = ("queued", "processing")


class CheckError(Exception):
    def __init__(self, code: str, status: int = 400, **extra):
        super().__init__(code)
        self.code = code
        self.status = status
        self.extra = extra


@dataclass
class IncomingFile:
    name: str
    data: bytes
    student_id: int | None = None


# ---------- Правила подтверждения ----------

def review_level(item: WorkCheckItem, settings: Settings) -> str:
    """one_click | review | manual — как интерфейс должен вести себя с работой."""
    if item.status == "failed" or item.confidence is None:
        return "manual"
    if item.confidence >= settings.check_one_click_confidence:
        return "one_click"
    if item.confidence >= settings.check_review_confidence:
        return "review"
    return "manual"


def confirm_blocker(item: WorkCheckItem, settings: Settings) -> str | None:
    """Почему работу пока нельзя подтвердить (None — можно)."""
    if item.status in ACTIVE:
        return "not_ready"
    level = review_level(item, settings)
    if level == "review" and item.viewed_at is None and item.teacher_score is None:
        return "open_required"  # жёлтая метка «Проверьте»: сначала открыть работу
    if level == "manual" and item.teacher_score is None:
        return "manual_required"  # уверенность < 70% или сбой — оценку ставит учитель
    return None


# ---------- Создание и чтение ----------

async def create_check(
    session: AsyncSession,
    teacher: User,
    *,
    title: str,
    files: list[IncomingFile],
    subject: str | None = None,
    grade: int | None = None,
    task_text: str | None = None,
    answer_key: str | None = None,
    max_score: int = 5,
    training_consent: bool = False,
    settings: Settings | None = None,
) -> WorkCheck:
    settings = settings or get_settings()
    if teacher.role != "teacher":
        raise CheckError("not_teacher", 403)
    if not files:
        raise CheckError("no_files", 422)
    if len(files) > settings.check_max_files:
        raise CheckError("too_many_files", 413, limit=settings.check_max_files)
    for f in files:
        if f.student_id is not None and not await is_linked_teacher(session, teacher.id, f.student_id):
            raise CheckError("student_not_linked", 403)

    saved: list[str] = []
    try:
        check = WorkCheck(
            teacher_user_id=teacher.id,
            title=title.strip()[:255] or "—",
            subject=subject,
            grade=grade,
            task_text=(task_text or "").strip()[:4000] or None,
            answer_key=(answer_key or "").strip()[:4000] or None,
            max_score=max_score,
            training_consent=training_consent,
            status="queued",
        )
        session.add(check)
        await session.flush()
        for f in files:
            mime = media.sniff_mime(f.data)
            if mime is None:
                raise CheckError("bad_file_type", 415, file=f.name)
            data, mime = await asyncio.to_thread(media.preprocess, f.data, mime)
            key = media.save(data, mime)
            saved.append(key)
            session.add(
                WorkCheckItem(
                    check_id=check.id,
                    student_user_id=f.student_id,
                    file_name=f.name[:255] or "work",
                    mime=mime,
                    storage_key=key,
                    status="queued",
                    attempts=0,
                )
            )
        await session.commit()
        return check
    except media.MediaError as exc:
        await session.rollback()
        for key in saved:
            media.delete(key)
        raise CheckError(exc.code, exc.status) from exc
    except Exception:
        await session.rollback()
        for key in saved:
            media.delete(key)
        raise


async def get_check(session: AsyncSession, teacher: User, check_id: int) -> WorkCheck:
    check = await session.get(WorkCheck, check_id)
    # Чужая проверка неотличима от несуществующей
    if check is None or check.teacher_user_id != teacher.id:
        raise CheckError("check_not_found", 404)
    return check


async def check_items(session: AsyncSession, check_id: int) -> list[WorkCheckItem]:
    rows = await session.scalars(
        select(WorkCheckItem).where(WorkCheckItem.check_id == check_id).order_by(WorkCheckItem.id)
    )
    return list(rows)


async def list_checks(session: AsyncSession, teacher: User, limit: int = 30) -> list[tuple[WorkCheck, dict]]:
    checks = list(
        await session.scalars(
            select(WorkCheck)
            .where(WorkCheck.teacher_user_id == teacher.id)
            .order_by(desc(WorkCheck.created_at), desc(WorkCheck.id))
            .limit(limit)
        )
    )
    counts: dict[int, dict] = {c.id: {} for c in checks}
    if checks:
        rows = await session.execute(
            select(WorkCheckItem.check_id, WorkCheckItem.status, func.count())
            .where(WorkCheckItem.check_id.in_(counts))
            .group_by(WorkCheckItem.check_id, WorkCheckItem.status)
        )
        for check_id, status, n in rows.all():
            counts[check_id][status] = n
    return [(c, counts[c.id]) for c in checks]


async def get_item(
    session: AsyncSession, teacher: User, check_id: int, item_id: int, *, mark_viewed: bool = False
) -> tuple[WorkCheck, WorkCheckItem]:
    check = await get_check(session, teacher, check_id)
    item = await session.get(WorkCheckItem, item_id)
    if item is None or item.check_id != check.id:
        raise CheckError("item_not_found", 404)
    if mark_viewed and item.viewed_at is None and item.status not in ACTIVE:
        item.viewed_at = utcnow()
        await session.commit()
    return check, item


async def update_item(
    session: AsyncSession,
    teacher: User,
    check_id: int,
    item_id: int,
    *,
    score: int | None = None,
    comment: str | None = None,
    marks: list | None = None,
    student_id: int | None = None,
) -> WorkCheckItem:
    """Правка учителем: оценка, комментарий, пометки, ученик. Результат ИИ не трогаем —
    пара «ИИ / учитель» и есть размеченные данные для дообучения."""
    check, item = await get_item(session, teacher, check_id, item_id)
    if item.confirmed_at is not None:
        raise CheckError("already_confirmed", 409)
    if item.status in ACTIVE:
        raise CheckError("not_ready", 409)
    if score is not None:
        if not 0 <= score <= check.max_score:
            raise CheckError("bad_score", 422, max_score=check.max_score)
        item.teacher_score = score
    if comment is not None:
        item.teacher_comment = comment.strip()[:2000]
    if marks is not None:
        clean = validate_result({"score": 0, "confidence": 100, "recognized_text": "x", "marks": marks}, check.max_score)
        item.teacher_marks = clean["marks"] if clean else []
    if student_id is not None:
        if not await is_linked_teacher(session, teacher.id, student_id):
            raise CheckError("student_not_linked", 403)
        item.student_user_id = student_id
    if item.status == "failed" and item.teacher_score is not None:
        item.status = "review"  # ИИ не справился, но учитель проверил вручную
    item.viewed_at = item.viewed_at or utcnow()
    await session.commit()
    return item


async def confirm(
    session: AsyncSession,
    teacher: User,
    check_id: int,
    item_ids: list[int] | None = None,
    settings: Settings | None = None,
) -> WorkCheck:
    """Подтверждение оценок. Если хоть одна выбранная работа не проходит правила
    уверенности — не подтверждается ничего (409 со списком причин)."""
    settings = settings or get_settings()
    check = await get_check(session, teacher, check_id)
    items = [i for i in await check_items(session, check.id) if i.confirmed_at is None]
    if item_ids is not None:
        wanted = set(item_ids)
        items = [i for i in items if i.id in wanted]
    if not items:
        raise CheckError("nothing_to_confirm", 409)
    blockers = {i.id: reason for i in items if (reason := confirm_blocker(i, settings))}
    if blockers:
        raise CheckError("confirm_blocked", 409, blockers=blockers)

    now = utcnow()
    for item in items:
        if item.teacher_score is None:
            item.teacher_score = item.ai_score  # учитель согласился с предложением ИИ
        item.status = "confirmed"
        item.confirmed_at = now
        if item.student_user_id is not None:
            await events_repo.enqueue(session, EVENT_WORK_GRADED, {"item_id": item.id})
    await session.flush()
    await _refresh_status(session, check)
    await session.commit()
    return check


# ---------- Обработчик очереди ----------

async def _refresh_status(session: AsyncSession, check: WorkCheck) -> tuple[str, str]:
    rows = await session.execute(
        select(WorkCheckItem.status, func.count()).where(WorkCheckItem.check_id == check.id).group_by(WorkCheckItem.status)
    )
    counts = dict(rows.all())
    total = sum(counts.values())
    before = check.status
    if total and counts.get("confirmed", 0) == total:
        status = "confirmed"
        check.confirmed_at = check.confirmed_at or utcnow()
    elif counts.get("processing") or (counts.get("queued") and total - counts.get("queued", 0) > 0):
        status = "processing"
    elif counts.get("queued"):
        status = "queued"
    elif total and counts.get("failed", 0) == total:
        status = "failed"
    else:
        status = "review"
    check.status = status
    return before, status


async def claim_items(session: AsyncSession, limit: int, settings: Settings) -> list[int]:
    """Забирает работы из очереди; зависшие (обработчик упал) возвращает в очередь."""
    stale = utcnow() - timedelta(seconds=settings.check_timeout_seconds * 3)
    await session.execute(
        update(WorkCheckItem)
        .where(WorkCheckItem.status == "processing", WorkCheckItem.started_at < stale)
        .values(status="queued")
    )
    stmt = (
        select(WorkCheckItem)
        .where(WorkCheckItem.status == "queued")
        .order_by(WorkCheckItem.created_at, WorkCheckItem.id)
        .limit(limit)
    )
    if is_postgres(session):
        stmt = stmt.with_for_update(skip_locked=True)
    items = list(await session.scalars(stmt))
    now = utcnow()
    for item in items:
        item.status = "processing"
        item.started_at = now
        item.attempts = (item.attempts or 0) + 1
    for check_id in {i.check_id for i in items}:
        check = await session.get(WorkCheck, check_id)
        if check is not None:
            await _refresh_status(session, check)
    await session.commit()
    return [i.id for i in items]


async def process_item(item_id: int, checker: WorkChecker, settings: Settings) -> int | None:
    """Проверяет одну работу; возвращает id пакета. Статус пакета здесь НЕ пересчитываем:
    параллельные работы одного пакета иначе «не видят» друг друга и пакет зависает."""
    async with SessionLocal() as session:
        item = await session.get(WorkCheckItem, item_id)
        if item is None or item.status != "processing":
            return None
        check = await session.get(WorkCheck, item.check_id)
        teacher = await session.get(User, check.teacher_user_id)
        task = CheckTask(
            task_text=check.task_text,
            answer_key=check.answer_key,
            max_score=check.max_score,
            subject=check.subject,
            grade=check.grade,
            lang=teacher.lang if teacher else "ru",
        )
        try:
            data = await asyncio.to_thread(media.load, item.storage_key)
            result = await asyncio.wait_for(
                checker.check_work(data, item.mime, task), timeout=settings.check_timeout_seconds
            )
            item.recognized_text = result["recognized_text"]
            item.ai_score = result["score"]
            item.ai_comment = result["comment"]
            item.ai_marks = result["marks"]
            item.confidence = result["confidence"]
            item.neatness = result["neatness"]
            item.error = None
            item.status = "review"
        except Exception as exc:  # сеть, таймаут, невалидный ответ модели
            log.warning("Проверка работы %s (попытка %s): %s", item.id, item.attempts, exc)
            item.error = str(exc)[:500]
            item.status = "failed" if item.attempts >= settings.check_max_attempts else "queued"
        await session.commit()
        return check.id


async def refresh_checks(check_ids: set[int]) -> None:
    """Пересчёт статусов пакетов после пачки — последовательно, со строковой блокировкой
    в PostgreSQL: уведомление «проверка готова» уходит учителю ровно один раз."""
    for check_id in sorted(check_ids):
        async with SessionLocal() as session:
            check = await session.get(WorkCheck, check_id, with_for_update=is_postgres(session))
            if check is None:
                continue
            before, after = await _refresh_status(session, check)
            if before != after and after in ("review", "failed"):
                await events_repo.enqueue(session, EVENT_CHECK_READY, {"check_id": check.id})
            await session.commit()


async def run_worker_once(checker: WorkChecker, settings: Settings | None = None) -> int:
    """Один проход: забрать до N работ и проверить их параллельно."""
    settings = settings or get_settings()
    async with SessionLocal() as session:
        ids = await claim_items(session, settings.check_concurrency, settings)
    if ids:
        done = await asyncio.gather(*(process_item(i, checker, settings) for i in ids))
        await refresh_checks({c for c in done if c is not None})
    return len(ids)


async def run_worker(checker: WorkChecker, settings: Settings | None = None, idle_seconds: float = 2.0) -> None:
    settings = settings or get_settings()
    log.info("Обработчик проверки работ запущен (параллельно: %s)", settings.check_concurrency)
    while True:
        try:
            if await run_worker_once(checker, settings):
                continue  # очередь не пуста — сразу следующая пачка
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Ошибка обработчика проверки работ")
        await asyncio.sleep(idle_seconds)
