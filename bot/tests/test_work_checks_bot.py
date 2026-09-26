"""Бот: уведомления Academic Copilot — учителю «проверка готова», родителю и ученику — оценка."""
from __future__ import annotations

import io

from PIL import Image

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.students import get_student
from app.repositories.users import get_by_telegram
from app.services import work_checks as svc
from app.services.vision import StubWorkChecker
from bot.events_worker import process_events_once
from test_bot_flow import KID, MOM, TEACHER, _student_with_consent


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (300, 200), (250, 250, 250)).save(buf, "JPEG")
    return buf.getvalue()


async def test_check_ready_then_grade_reaches_parent_and_student(h):
    kid_id = await _student_with_consent(h)
    async with SessionLocal() as s:
        code = (await get_student(s, kid_id)).family_code
    await h.send(TEACHER, "/start", name="Учитель")
    await h.register(TEACHER, "teacher", name="Учитель")
    await h.press(TEACHER, "teacher:bind", name="Учитель")
    await h.send(TEACHER, code, name="Учитель")

    async with SessionLocal() as s:
        teacher = await get_by_telegram(s, TEACHER)
        check = await svc.create_check(
            s, teacher, title="Трапеция", max_score=5,
            files=[svc.IncomingFile("aziza.jpg", _jpeg(), kid_id)],
        )
    settings = get_settings()
    while await svc.run_worker_once(StubWorkChecker(), settings):
        pass

    await process_events_once(h.bot)
    ready = h.api.last(TEACHER)
    assert "ИИ проверил работы" in ready.text and "«Трапеция»: 1" in ready.text
    # сайт на HTTPS — кнопка «Открыть проверку» ведёт в Mini App
    assert [b.web_app.url for b in h.buttons(ready) if b.web_app] == [f"https://edu.example.com/teacher/checks/{check.id}"]

    # До подтверждения учителем родитель ничего не получает
    assert not any("проверил работу" in t for t in h.api.texts(MOM))

    async with SessionLocal() as s:
        teacher = await get_by_telegram(s, TEACHER)
        [item] = await svc.check_items(s, check.id)
        await svc.update_item(s, teacher, check.id, item.id, score=4, comment="Молодец, но проверь единицы")
        await svc.confirm(s, teacher, check.id)
    await process_events_once(h.bot)
    parent = h.api.last(MOM).text
    assert "Учитель проверил работу «Трапеция»" in parent and "4 из 5" in parent and "проверь единицы" in parent
    assert "Твоя работа «Трапеция» проверена: <b>4 из 5</b>" in h.api.last(KID).text
