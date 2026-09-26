"""IELTS AI Coach: Writing — два экзаменатора, Band по правилам IELTS, ошибки только из эссе."""
from __future__ import annotations

from app.db.models import Student
from app.db.session import SessionLocal
from app.main import app
from app.services.ielts import count_words, overall_band
from test_api import KID_TG, login, make_student

ESSAY = (
    "nowadays many students learn online. " * 52
    + "In conclusion, school gives discipline and friends, so I believe it is better than studying at home."
)


async def _senior(grade: int | None = 11) -> dict:
    kid_id = await make_student()
    async with SessionLocal() as s:
        (await s.get(Student, kid_id)).grade = grade
        await s.commit()
    return kid_id


def test_ielts_band_rounding():
    assert overall_band([6.0, 6.5, 6.5, 6.0]) == 6.5  # 6.25 → 6.5
    assert overall_band([7.0, 7.0, 6.5, 6.5]) == 7.0  # 6.75 → 7.0
    assert overall_band([6.0, 6.0, 6.0, 6.5]) == 6.0  # 6.125 → 6.0
    assert overall_band([5.5, 6.0]) == 6.0  # 5.75 → 6.0
    assert count_words("It's a well-known fact, isn't it?") == 6


async def test_writing_task2_flow(client):
    await _senior()
    headers = await login(client)
    r = await client.post("/api/ielts/writing", json={"task": 2}, headers=headers)
    assert r.status_code == 200, r.text
    attempt = r.json()
    assert attempt["material"]["task"] == 2 and attempt["limits"] == {"minutes": 40, "min_words": 250}
    # Незаконченное эссе — тот же вариант, черновик сохраняется
    assert (await client.put(f"/api/ielts/attempts/{attempt['id']}/draft", json={"text": "draft"}, headers=headers)).json() == {"ok": True}
    again = (await client.post("/api/ielts/writing", json={"task": 2}, headers=headers)).json()
    assert again["id"] == attempt["id"] and again["answers"]["text"] == "draft"

    short = await client.post(f"/api/ielts/attempts/{attempt['id']}/submit", json={"text": "too short"}, headers=headers)
    assert short.status_code == 422 and short.json()["detail"]["code"] == "essay_too_short"

    done = (await client.post(f"/api/ielts/attempts/{attempt['id']}/submit", json={"text": ESSAY}, headers=headers)).json()
    result = done["result"]
    assert done["status"] == "done"
    assert result["examiners"]["A"]["LR"] == 6.5 and result["examiners"]["B"]["LR"] == 6.0
    assert result["criteria"]["LR"]["band"] == 6.5  # среднее 6.25 → 6.5 по правилу IELTS
    assert done["band"] == 6.5
    assert [e["quote"] for e in result["errors"]] == ["nowadays many students"]  # выдуманная цитата отброшена
    assert result["words"] == count_words(ESSAY) and not result["under_length"]

    assert (await client.post(f"/api/ielts/attempts/{attempt['id']}/submit", json={"text": ESSAY}, headers=headers)).status_code == 409
    overview = (await client.get("/api/ielts", headers=headers)).json()
    assert overview["best"] == {"writing": 6.5}
    # Задание пройдено — следующий Task 2 будет новым (ИИ генерирует, банк растёт)
    nxt = (await client.post("/api/ielts/writing", json={"task": 2}, headers=headers)).json()
    assert nxt["id"] != attempt["id"] and nxt["status"] == "active"


async def test_writing_task1_has_chart_and_short_essay_penalty(client):
    await _senior()
    headers = await login(client)
    attempt = (await client.post("/api/ielts/writing", json={"task": 1}, headers=headers)).json()
    chart = attempt["material"]["chart"]
    assert chart["type"] == "bar" and len(chart["series"][0]["values"]) == len(chart["labels"])
    text = "the chart shows internet access in three countries. " * 12  # ~96 слов < 150
    done = (await client.post(f"/api/ielts/attempts/{attempt['id']}/submit", json={"text": text}, headers=headers)).json()
    assert done["result"]["under_length"] and done["band"] == 5.0


async def test_ielts_rules_and_access(client):
    kid_id = await _senior(grade=8)
    headers = await login(client)
    r = await client.post("/api/ielts/writing", json={"task": 2}, headers=headers)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "ielts_grade"
    async with SessionLocal() as s:
        (await s.get(Student, kid_id)).grade = 10
        await s.commit()
    attempt = (await client.post("/api/ielts/writing", json={"task": 2}, headers=headers)).json()

    app.state.explain.lesson.fail_next = False
    await make_student(tg_id=6000)
    other = await login(client, 6000)
    assert (await client.get(f"/api/ielts/attempts/{attempt['id']}", headers=other)).status_code == 404
    assert (await client.put(f"/api/ielts/attempts/{attempt['id']}/draft", json={"text": "x"}, headers=other)).status_code == 404
    assert (await client.post(f"/api/ielts/attempts/{attempt['id']}/submit", json={"text": ESSAY}, headers=other)).status_code == 404
    parent = await login(client, KID_TG + 1)
    assert (await client.get("/api/ielts", headers=parent)).status_code == 403


async def test_writing_uses_daily_limit_and_refunds(client, monkeypatch):
    await _senior()
    headers = await login(client)
    attempt = (await client.post("/api/ielts/writing", json={"task": 2}, headers=headers)).json()
    lesson = app.state.explain.lesson

    async def broken(*args, **kwargs):
        raise RuntimeError("model down")

    monkeypatch.setattr(lesson, "ielts_grade_writing", broken)
    before = (await client.get("/api/progress", headers=headers)).json()["explanations_left_today"]
    r = await client.post(f"/api/ielts/attempts/{attempt['id']}/submit", json={"text": ESSAY}, headers=headers)
    assert r.status_code == 502
    after = (await client.get("/api/progress", headers=headers)).json()
    assert after["explanations_left_today"] == before  # попытка вернулась
    saved = (await client.get(f"/api/ielts/attempts/{attempt['id']}", headers=headers)).json()
    assert saved["status"] == "active" and saved["answers"]["text"] == ESSAY.strip()  # эссе не потерялось


def test_test_band_tables_and_answer_check():
    from app.services.gemini import ielts_answer_ok
    from app.services.ielts import test_band

    assert test_band("reading", 13, 13) == 9.0
    assert test_band("reading", 10, 13) == 7.0  # 31 из 40
    assert test_band("reading", 5, 13) == 5.0 and test_band("listening", 5, 13) == 4.5  # 15 из 40: шкалы разные
    assert test_band("reading", 0, 13) == 0.0
    gap = {"type": "gap", "answer": "iron", "alternatives": ["wrought iron"]}
    assert ielts_answer_ok(gap, " Wrought IRON. ") and not ielts_answer_ok(gap, "steel")
    assert ielts_answer_ok({"type": "tfng", "answer": "NOT GIVEN"}, "not given")
    assert not ielts_answer_ok({"type": "mcq", "answer": 1}, True)  # bool — не индекс


async def test_reading_test_flow(client):
    await _senior()
    headers = await login(client)
    r = await client.post("/api/ielts/tests", json={"kind": "reading"}, headers=headers)
    assert r.status_code == 200, r.text
    attempt = r.json()
    qs = attempt["material"]["questions"]
    assert len(qs) == 11 and all("answer" not in q and "evidence" not in q for q in qs)  # ключ скрыт

    answers = {str(i): 0 for i in range(6)}  # все mcq верно
    answers.update({"6": "TRUE", "7": "TRUE", "8": "not given", "9": "1889", "10": "Wrought iron"})
    done = (await client.post(f"/api/ielts/attempts/{attempt['id']}/answers", json={"answers": answers}, headers=headers)).json()
    assert done["result"]["correct"] == 10 and done["result"]["marks"][7] is False  # «FALSE» ответили «TRUE»
    assert done["band"] == 8.0  # 10/11 → 36 из 40
    assert all("answer" in q for q in done["material"]["questions"])  # после — ключ и доказательства
    again = await client.post(f"/api/ielts/attempts/{attempt['id']}/answers", json={"answers": answers}, headers=headers)
    assert again.status_code == 409

    await make_student(tg_id=6000)
    other = await login(client, 6000)
    assert (await client.get(f"/api/ielts/attempts/{attempt['id']}", headers=other)).status_code == 404
    r = await client.post(f"/api/ielts/attempts/{attempt['id']}/answers", json={"answers": {}}, headers=other)
    assert r.status_code == 404


async def test_listening_test_has_script_and_bands(client):
    await _senior()
    headers = await login(client)
    attempt = (await client.post("/api/ielts/tests", json={"kind": "listening"}, headers=headers)).json()
    material = attempt["material"]
    assert material["script"] and material["context"] and len(material["questions"]) == 11
    done = (await client.post(f"/api/ielts/attempts/{attempt['id']}/answers", json={"answers": {}}, headers=headers)).json()
    assert done["result"]["correct"] == 0 and done["band"] == 0.0
    overview = (await client.get("/api/ielts", headers=headers)).json()
    assert overview["best"] == {"listening": 0.0}
    assert (await client.post("/api/ielts/tests", json={"kind": "math"}, headers=headers)).status_code == 422


WAV = b"RIFF" + b"\x01" * 400  # «речь» для заглушки (тишина — одни нули)


async def _speak(client, headers, attempt_id: int, turn: int, data: bytes = WAV, mime: str = "audio/wav"):
    return await client.post(
        f"/api/ielts/attempts/{attempt_id}/speak",
        data={"turn": str(turn)},
        files={"audio": ("answer.wav", data, mime)},
        headers=headers,
    )


async def test_speaking_exam_flow(client):
    await _senior()
    headers = await login(client)
    before = (await client.get("/api/progress", headers=headers)).json()["explanations_left_today"]
    attempt = (await client.post("/api/ielts/speaking", headers=headers)).json()
    plan = attempt["plan"]
    assert [p["part"] for p in plan] == [1, 1, 1, 1, 2, 3, 3, 3, 3]
    assert plan[4]["question"].startswith("Describe a hobby")
    after = (await client.get("/api/progress", headers=headers)).json()["explanations_left_today"]
    assert after == before - 1  # весь экзамен — одна попытка

    silent = await _speak(client, headers, attempt["id"], 0, b"\x00" * 400)
    assert silent.status_code == 422 and silent.json()["detail"]["code"] == "no_speech"
    assert (await _speak(client, headers, attempt["id"], 3)).status_code == 409  # не тот вопрос

    r = (await _speak(client, headers, attempt["id"], 0)).json()
    turn = r["answers"]["turns"][0]
    assert turn["transcript"].startswith("I likes")
    assert [g["quote"] for g in turn["grammar"]] == ["I likes"]  # «he go» нет в ответе — отброшено
    assert [p["word"] for p in turn["pronunciation"]] == ["weekend"]
    for i in range(1, 9):
        r = await _speak(client, headers, attempt["id"], i)
        assert r.status_code == 200, r.text
    done = r.json()
    assert done["status"] == "done"
    assert done["result"]["criteria"]["LR"]["band"] == 6.5  # 6.5 и 6.0 → 6.25 → 6.5
    assert done["band"] == 6.0  # (6 + 6.5 + 5.5 + 6) / 4 = 6.0
    assert (await _speak(client, headers, attempt["id"], 9)).status_code == 409

    bad = await client.post(f"/api/ielts/attempts/{attempt['id']}/speak", data={"turn": "0"},
                            files={"audio": ("x.txt", b"hi", "text/plain")}, headers=headers)
    assert bad.status_code == 415


async def test_speaking_access(client):
    await _senior()
    attempt = (await client.post("/api/ielts/speaking", headers=await login(client))).json()
    await make_student(tg_id=6000)
    other = await login(client, 6000)
    assert (await _speak(client, other, attempt["id"], 0)).status_code == 404
    assert (await client.post(f"/api/ielts/attempts/{attempt['id']}/grade", headers=other)).status_code == 404
