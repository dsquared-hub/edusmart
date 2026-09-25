"""Academic Copilot (Модуль 5.1): ИИ-проверка рукописных работ."""
from __future__ import annotations

import io
from datetime import timedelta

import pytest
from PIL import Image
from sqlalchemy import select

from app.core.config import get_settings
from app.core.timeutil import utcnow
from app.db.models import Event, WorkCheckItem
from app.db.session import SessionLocal
from app.repositories.students import link_teacher
from app.repositories.users import upsert_telegram_user
from app.services import media
from app.services import work_checks as svc
from app.services.accounts import choose_role
from app.services.gemini import GeminiError
from app.services.vision import validate_result
from test_api import login, make_student

TEACHER_TG, OTHER_TEACHER_TG = 4100, 4200
SETTINGS = get_settings().model_copy(update={"check_concurrency": 1})


def jpeg(color=(250, 250, 250), size=(400, 300)) -> bytes:
    img = Image.new("RGB", size, color)
    for x in range(60, 340):  # «строка текста», чтобы обрезка полей не съела всё
        img.putpixel((x, 150), (20, 20, 20))
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


class ScriptedChecker:
    """Выдаёт заранее заданные ответы по порядку вызовов; Exception — сбой модели."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)

    async def check_work(self, file, mime, task):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return validate_result(
            {"recognized_text": "S = 32", "score": outcome.get("score", 4), "confidence": outcome["confidence"],
             "neatness": 75, "comment": "Молодец", "marks": [{"box": [0.1, 0.2, 0.3, 0.1], "type": "calculation", "note": "x"}]},
            task.max_score,
        )


async def teacher(tg: int = TEACHER_TG) -> int:
    async with SessionLocal() as s:
        user = await upsert_telegram_user(s, tg, None, "Учитель")
        await choose_role(s, user, "teacher")
        await s.commit()
        return user.id


async def drain(checker) -> None:
    while await svc.run_worker_once(checker, SETTINGS):
        pass


async def upload(client, headers, files, **form):
    data = {"title": "Контрольная: трапеция", "subject": "math", "grade": "7", "max_score": "5",
            "task_text": "Найдите площадь трапеции", "answer_key": "32", **form}
    return await client.post(
        "/api/v1/teacher/checks",
        data=data,
        files=[("files", (name, content, "image/jpeg")) for name, content in files],
        headers=headers,
    )


async def test_full_flow_with_confidence_rules(client):
    kid_id = await make_student()
    teacher_id = await teacher()
    async with SessionLocal() as s:
        await link_teacher(s, teacher_id, kid_id)
        await s.commit()
    headers = await login(client, TEACHER_TG)

    files = [("aziza.jpg", jpeg((250, 250, 250))), ("b.jpg", jpeg((245, 245, 240))), ("c.jpg", jpeg((240, 240, 235)))]
    r = await upload(client, headers, files, student_ids=[str(kid_id), "0", "0"])
    assert r.status_code == 200, r.text
    check_id = r.json()["check_id"]
    assert r.json() == {"check_id": check_id, "status": "queued", "items": 3}

    body = (await client.get(f"/api/v1/teacher/checks/{check_id}", headers=headers)).json()
    assert [i["status"] for i in body["items"]] == ["queued"] * 3
    assert body["items"][0]["student_id"] == kid_id and body["items"][0]["level"] is None

    await drain(ScriptedChecker({"confidence": 95, "score": 5}, {"confidence": 80}, {"confidence": 55}))
    body = (await client.get(f"/api/v1/teacher/checks/{check_id}", headers=headers)).json()
    assert body["status"] == "review"
    one, review, manual = body["items"]
    assert (one["level"], review["level"], manual["level"]) == ("one_click", "review", "manual")
    assert (one["blocker"], review["blocker"], manual["blocker"]) == (None, "open_required", "manual_required")
    # фильтр очереди по уверенности
    only = (await client.get(f"/api/v1/teacher/checks/{check_id}?level=review", headers=headers)).json()["items"]
    assert [i["id"] for i in only] == [review["id"]]

    # «Всё сразу» нельзя: ничего не подтверждается, причины — по каждой работе
    r = await client.post(f"/api/v1/teacher/checks/{check_id}/confirm", json={}, headers=headers)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "confirm_blocked"
    assert r.json()["detail"]["blockers"] == {str(review["id"]): "open_required", str(manual["id"]): "manual_required"}

    # ≥90% — в один клик; оценка уходит родителю через очередь событий
    r = await client.post(f"/api/v1/teacher/checks/{check_id}/confirm", json={"item_ids": [one["id"]]}, headers=headers)
    assert r.status_code == 200 and r.json()["status"] == "review"
    async with SessionLocal() as s:
        graded = list(await s.scalars(select(Event).where(Event.type == svc.EVENT_WORK_GRADED)))
        assert [e.payload for e in graded] == [{"item_id": one["id"]}]

    # 70–89% — после открытия работы
    opened = (await client.get(f"/api/v1/teacher/checks/{check_id}/items/{review['id']}", headers=headers)).json()
    assert opened["viewed"] and opened["recognized_text"] == "S = 32" and opened["ai_marks"][0]["type"] == "calculation"
    # <70% — только после ручной оценки учителя
    r = await client.patch(
        f"/api/v1/teacher/checks/{check_id}/items/{manual['id']}",
        json={"score": 3, "comment": "Проверь вторую строку"},
        headers=headers,
    )
    assert r.status_code == 200 and r.json()["teacher_score"] == 3 and r.json()["ai_score"] == 4

    r = await client.post(f"/api/v1/teacher/checks/{check_id}/confirm", json={}, headers=headers)
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    finals = {i["id"]: i["final_score"] for i in r.json()["items"]}
    assert finals == {one["id"]: 5, review["id"]: 4, manual["id"]: 3}

    # После подтверждения менять оценку нельзя
    r = await client.patch(f"/api/v1/teacher/checks/{check_id}/items/{manual['id']}", json={"score": 5}, headers=headers)
    assert r.status_code == 409

    async with SessionLocal() as s:
        ready = list(await s.scalars(select(Event).where(Event.type == svc.EVENT_CHECK_READY)))
        assert len(ready) == 1  # «проверка готова» — ровно одно уведомление

    # Фото работы доступно учителю (для пометок поверх)
    r = await client.get(f"/api/v1/teacher/checks/{check_id}/items/{one['id']}/file", headers=headers)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content[:3] == b"\xff\xd8\xff"

    listing = (await client.get("/api/v1/teacher/checks", headers=headers)).json()["checks"]
    assert listing[0]["id"] == check_id and listing[0]["counts"] == {"confirmed": 3}


async def test_access_control(client):
    kid_id = await make_student()
    await teacher()
    await teacher(OTHER_TEACHER_TG)
    headers = await login(client, TEACHER_TG)

    # Ученик, не привязанный к учителю
    r = await upload(client, headers, [("a.jpg", jpeg())], student_ids=[str(kid_id)])
    assert r.status_code == 403 and r.json()["detail"]["code"] == "student_not_linked"

    check_id = (await upload(client, headers, [("a.jpg", jpeg())])).json()["check_id"]
    other = await login(client, OTHER_TEACHER_TG)
    for path in ("", "/items/1", "/items/1/file"):
        assert (await client.get(f"/api/v1/teacher/checks/{check_id}{path}", headers=other)).status_code == 404
    assert (await client.post(f"/api/v1/teacher/checks/{check_id}/confirm", json={}, headers=other)).status_code == 404

    student = await login(client)  # ученик не может загружать работы
    r = await upload(client, student, [("a.jpg", jpeg())])
    assert r.status_code == 403 and r.json()["detail"]["code"] == "not_teacher"
    assert (await client.get("/api/v1/teacher/checks", headers=student)).status_code == 403


async def test_file_validation_leaves_no_garbage(client):
    await teacher()
    headers = await login(client, TEACHER_TG)
    before = set((media._root()).iterdir())

    # Первый файл нормальный, второй — не картинка: пакет не создаётся, файлы не остаются
    r = await upload(client, headers, [("a.jpg", jpeg()), ("virus.jpg", b"MZ\x90\x00 not an image")])
    assert r.status_code == 415 and r.json()["detail"] == {"code": "bad_file_type", "file": "virus.jpg"}
    assert set(media._root().iterdir()) == before
    assert (await client.get("/api/v1/teacher/checks", headers=headers)).json()["checks"] == []

    r = await upload(client, headers, [(f"{n}.jpg", jpeg()) for n in range(41)])
    assert r.status_code == 413 and r.json()["detail"]["code"] == "too_many_files"

    # PDF принимается как есть
    r = await client.post(
        "/api/v1/teacher/checks",
        data={"title": "PDF"},
        files=[("files", ("work.pdf", b"%PDF-1.4\n%fake\n", "application/pdf"))],
        headers=headers,
    )
    assert r.status_code == 200


async def test_retries_then_failed_then_manual(client):
    await teacher()
    headers = await login(client, TEACHER_TG)
    check_id = (await upload(client, headers, [("a.jpg", jpeg())])).json()["check_id"]

    # Два сбоя, затем успех — работа всё равно проверена
    await drain(ScriptedChecker(GeminiError("timeout"), GeminiError("bad json"), {"confidence": 92}))
    item = (await client.get(f"/api/v1/teacher/checks/{check_id}", headers=headers)).json()["items"][0]
    assert item["status"] == "review" and item["level"] == "one_click"

    # Три сбоя подряд — failed; учитель ставит оценку вручную и подтверждает
    check2 = (await upload(client, headers, [("b.jpg", jpeg((200, 200, 200)))])).json()["check_id"]
    await drain(ScriptedChecker(*[GeminiError("down")] * 3))
    body = (await client.get(f"/api/v1/teacher/checks/{check2}", headers=headers)).json()
    assert body["status"] == "failed" and body["items"][0]["error"] == "down"
    assert body["items"][0]["level"] == "manual"
    item_id = body["items"][0]["id"]
    await client.patch(f"/api/v1/teacher/checks/{check2}/items/{item_id}", json={"score": 4}, headers=headers)
    r = await client.post(f"/api/v1/teacher/checks/{check2}/confirm", json={}, headers=headers)
    assert r.status_code == 200 and r.json()["items"][0]["final_score"] == 4


async def test_stale_processing_is_requeued(client):
    await teacher()
    headers = await login(client, TEACHER_TG)
    check_id = (await upload(client, headers, [("a.jpg", jpeg())])).json()["check_id"]
    async with SessionLocal() as s:  # обработчик «упал» посреди работы
        item = await s.scalar(select(WorkCheckItem).where(WorkCheckItem.check_id == check_id))
        item.status, item.started_at = "processing", utcnow() - timedelta(hours=1)
        await s.commit()
    await drain(ScriptedChecker({"confidence": 99}))
    item = (await client.get(f"/api/v1/teacher/checks/{check_id}", headers=headers)).json()["items"][0]
    assert item["status"] == "review"


def test_preprocess_and_sniff():
    big = Image.new("RGB", (4000, 3000), (255, 255, 255))
    for x in range(500, 3500):
        big.putpixel((x, 1500), (0, 0, 0))
    buf = io.BytesIO()
    big.save(buf, "PNG")
    data, mime = media.preprocess(buf.getvalue(), "image/png")
    assert mime == "image/jpeg" and data[:3] == b"\xff\xd8\xff"
    assert max(Image.open(io.BytesIO(data)).size) <= media.MAX_SIDE

    assert media.sniff_mime(b"\x00\x00\x00\x18ftypheic....") == "image/heic"
    assert media.sniff_mime(b"GIF89a") is None
    with pytest.raises(media.MediaError):
        media.load("../../etc/passwd")


def test_validate_result_is_strict():
    assert validate_result({"score": 6, "confidence": 90, "recognized_text": "x"}, 5) is None
    assert validate_result({"score": 3, "confidence": "high", "recognized_text": "x"}, 5) is None
    r = validate_result(
        {"score": 3, "confidence": 97, "recognized_text": "", "marks": [
            {"box": [0.9, 0.9, 0.5, 0.5], "type": "weird", "note": "n"}, {"box": [1, 2]}]},
        5,
    )
    assert r["confidence"] == 40  # ничего не распознано — уверенность урезана
    assert r["marks"] == [{"box": [0.9, 0.9, 0.1, 0.1], "type": "other", "note": "n"}]
