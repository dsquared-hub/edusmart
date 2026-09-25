"""Academic Copilot (Модуль 5.2): учебники, RAG и генерация материалов урока."""
from __future__ import annotations

import io

import pymupdf
from docx import Document

from app.db.models import Textbook
from app.db.session import SessionLocal
from app.repositories.users import upsert_telegram_user
from app.services.accounts import choose_role
from app.services.materials import validate_material
from app.services.rag import chunk_pages
from test_api import login, make_student

TEACHER_TG, OTHER_TG = 5100, 5200

PAGES = [
    "Kasrlar. Kasr butunning qismini bildiradi. Surat va maxraj haqida. " * 6,
    "Trapetsiya yuzi. Trapetsiyaning yuzi asoslar yigindisining yarmini balandlikka "
    "kopaytirishga teng: S = (a + b) / 2 * h. Trapetsiya asoslari parallel. " * 5,
    "Uchburchak. Uchburchakning ichki burchaklari yigindisi 180 gradus. " * 6,
]


def make_pdf(pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(40, 40, 555, 800), text, fontsize=11)
    return doc.tobytes()


async def teacher(tg: int = TEACHER_TG) -> None:
    async with SessionLocal() as s:
        user = await upsert_telegram_user(s, tg, None, "Учитель")
        await choose_role(s, user, "teacher")
        await s.commit()


async def upload(client, headers, pdf: bytes, **form):
    data = {"title": "Geometriya 7", "subject": "math", "grade": "7", "license_note": "Своя копия для урока", **form}
    return await client.post(
        "/api/v1/teacher/textbooks", data=data, files={"file": ("book.pdf", pdf, "application/pdf")}, headers=headers
    )


async def test_upload_index_generate_edit_export(client):
    await teacher()
    headers = await login(client, TEACHER_TG)

    r = await upload(client, headers, make_pdf(PAGES))
    assert r.status_code == 200, r.text
    book_id = r.json()["id"]
    assert r.json()["status"] == "processing"
    book = (await client.get(f"/api/v1/teacher/textbooks/{book_id}", headers=headers)).json()
    assert book["status"] == "ready" and book["pages"] == 3  # фоновая индексация завершилась

    r = await client.post(
        "/api/v1/teacher/materials",
        json={"textbook_id": book_id, "topic": "Trapetsiya yuzi", "variants": 3, "lang": "ru"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    m = r.json()
    c = m["content"]
    assert sum(s["minutes"] for s in c["plan"]["stages"]) == 45
    assert 8 <= len(c["stories"]) <= 12
    assert [v["name"] for v in c["test"]["variants"]] == ["A", "B", "C"]
    assert len(c["answer_key"]) == sum(len(v["tasks"]) for v in c["test"]["variants"])
    # Источник — страница про трапецию, и только реальные страницы учебника
    assert 2 in m["sources"] and set(m["sources"]) <= {1, 2, 3}
    assert "Trapetsiya" in " ".join(s["text"] for s in c["stories"])  # опора на текст учебника

    # Учитель правит задачу — ключ ответов пересобирается
    c["test"]["variants"][0]["tasks"][0]["answer"] = "32 см²"
    r = await client.put(f"/api/v1/teacher/materials/{m['id']}", json={"content": c, "topic": "Площадь трапеции"}, headers=headers)
    assert r.status_code == 200 and r.json()["topic"] == "Площадь трапеции"
    assert r.json()["content"]["answer_key"][0]["answer"] == "32 см²"
    broken = {**c, "stories": c["stories"][:2]}
    assert (await client.put(f"/api/v1/teacher/materials/{m['id']}", json={"content": broken}, headers=headers)).status_code == 422

    r = await client.get(f"/api/v1/teacher/materials/{m['id']}/export.docx", headers=headers)
    assert r.status_code == 200 and r.content[:2] == b"PK"
    text = "\n".join(p.text for p in Document(io.BytesIO(r.content)).paragraphs)
    assert "Площадь трапеции" in text and "Ключ ответов" in text and "32 см²" in text

    listing = (await client.get("/api/v1/teacher/materials", headers=headers)).json()["materials"]
    assert [x["id"] for x in listing] == [m["id"]] and "content" not in listing[0]


async def test_no_invention_and_bad_files(client):
    await teacher()
    headers = await login(client, TEACHER_TG)
    book_id = (await upload(client, headers, make_pdf(PAGES))).json()["id"]

    # В учебнике нет ничего про фотосинтез — урок не выдумываем
    r = await client.post("/api/v1/teacher/materials", json={"textbook_id": book_id, "topic": "Fotosintez xloroplast"}, headers=headers)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "topic_not_in_textbook"

    r = await upload(client, headers, b"\x89PNG\r\n\x1a\nnot a pdf")
    assert r.status_code == 415 and r.json()["detail"]["code"] == "need_pdf"

    # Скан без текстового слоя — нужен OCR, честно сообщаем
    scan_id = (await upload(client, headers, make_pdf(["", ""]))).json()["id"]
    scan = (await client.get(f"/api/v1/teacher/textbooks/{scan_id}", headers=headers)).json()
    assert scan["status"] == "failed" and scan["error"] == "no_text_layer"
    r = await client.post("/api/v1/teacher/materials", json={"textbook_id": scan_id, "topic": "x"}, headers=headers)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "textbook_not_ready"

    # Права на контент — обязательное поле
    r = await client.post(
        "/api/v1/teacher/textbooks", data={"title": "X"}, files={"file": ("b.pdf", make_pdf(PAGES), "application/pdf")}, headers=headers
    )
    assert r.status_code == 422


async def test_access_and_library(client):
    await make_student()
    await teacher()
    await teacher(OTHER_TG)
    mine = await login(client, TEACHER_TG)
    other = await login(client, OTHER_TG)
    book_id = (await upload(client, mine, make_pdf(PAGES))).json()["id"]
    material_id = (
        await client.post("/api/v1/teacher/materials", json={"textbook_id": book_id, "topic": "Trapetsiya yuzi"}, headers=mine)
    ).json()["id"]

    assert (await client.get(f"/api/v1/teacher/textbooks/{book_id}", headers=other)).status_code == 404
    assert (await client.get(f"/api/v1/teacher/materials/{material_id}", headers=other)).status_code == 404
    assert (await client.get(f"/api/v1/teacher/materials/{material_id}/export.docx", headers=other)).status_code == 404
    assert (await client.get("/api/v1/teacher/textbooks", headers=await login(client))).status_code == 403  # ученик

    # Учебник библиотеки платформы (owner = NULL) виден всем учителям, но не удаляется ими
    async with SessionLocal() as s:
        lib = Textbook(owner_teacher_id=None, title="Библиотека", pages=0, status="ready")
        s.add(lib)
        await s.commit()
        lib_id = lib.id
    titles = [b["title"] for b in (await client.get("/api/v1/teacher/textbooks", headers=other)).json()["textbooks"]]
    assert titles == ["Библиотека"]
    assert (await client.delete(f"/api/v1/teacher/textbooks/{lib_id}", headers=other)).status_code == 403
    assert (await client.delete(f"/api/v1/teacher/textbooks/{book_id}", headers=mine)).json() == {"ok": True}


def test_validate_material_rules():
    base = {
        "plan": {"title": "T", "goals": ["g"], "stages": [{"name": "a", "minutes": 20, "activity": "x"}, {"name": "b", "minutes": 15, "activity": "y"}, {"name": "c", "minutes": 7, "activity": "z"}]},
        "stories": [{"title": f"s{i}", "text": "t", "question": "q", "options": ["1", "2"], "correct": 5} for i in range(8)],
        "test": {"variants": [{"name": "A", "tasks": [{"text": "t", "points": 2, "answer": "1"}] * 3}] * 2},
        "sources": [2, 99],
    }
    r = validate_material(base, 2, {2, 3})
    assert r["plan"]["stages"][-1]["minutes"] == 10  # 42 минуты → подогнано до 45
    assert r["sources"] == [2]  # несуществующая страница 99 отброшена
    assert "question" not in r["stories"][0]  # неверный индекс ответа — вопрос убран, слайд оставлен
    assert validate_material(base, 3, {2}) is None  # просили 3 варианта, пришло 2


def test_chunks_never_cross_pages():
    chunks = chunk_pages(["a " * 1000, "b " * 30 + "конец страницы два", "12"])
    assert {p for p, _ in chunks} == {1, 2}  # «12» — номер страницы, не фрагмент
    assert all(("b" not in t) for p, t in chunks if p == 1)
    assert len([p for p, _ in chunks if p == 1]) >= 3  # длинная страница — несколько фрагментов
