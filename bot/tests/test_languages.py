"""Языки бота: ru / uz / en — выбор, автоопределение, рассылки на языке получателя."""
from __future__ import annotations

from app.db.session import SessionLocal
from app.repositories.users import get_by_telegram
from bot.events_worker import process_events_once
from test_bot_flow import CORRECT, KID, MOM, _student_with_consent, _topic


async def test_new_user_language_from_telegram(h):
    await h.send(5001, "/start", lang="en")
    assert "Who are you?" in h.api.last(5001).text
    await h.send(5002, "/start", lang="uz")
    assert "Siz kimsiz?" in h.api.last(5002).text
    await h.send(5003, "/start", lang="de")  # нет такого — русский
    assert "Кто вы?" in h.api.last(5003).text


async def test_switch_language_in_menu(h):
    await h.send(KID, "/start")
    assert "lang:menu" in h.callback_data(h.api.last(KID))
    await h.press(KID, "lang:menu")
    assert h.callback_data(h.api.last(KID)) == ["lang:set:ru", "lang:set:uz", "lang:set:en"]

    await h.press(KID, "lang:set:uz")
    texts = h.api.texts(KID)
    assert "oʻzbekcha" in texts[-2]
    assert "Siz kimsiz?" in texts[-1]  # меню уже на узбекском
    async with SessionLocal() as s:
        assert (await get_by_telegram(s, KID)).lang == "uz"  # общий с сайтом профиль

    # Выбор сохраняется, даже если в Telegram другой язык
    await h.send(KID, "/start", lang="en")
    assert "Siz kimsiz?" in h.api.last(KID).text


async def test_explanation_flow_in_english(h):
    kid_id = await _student_with_consent(h)
    await h.press(KID, "lang:set:en")
    await h.press(KID, "student:help")
    assert "Tell me what you didn't get" in h.api.last(KID).text
    await h.send(KID, "fractions")
    assert "Let me explain: fractions" in h.api.last(KID).text
    topic = await _topic(kid_id)
    await h.press(KID, f"quiz:{topic.id}")
    assert "Question 1 of 4" in h.api.last(KID).text
    await h.press(KID, f"ans:{topic.id}:0:{CORRECT[0]}")
    review = h.api.last(KID).text
    assert "Correct! +10 points" in review and "You chose:" in review


async def test_parent_notified_in_parent_language(h):
    kid_id = await _student_with_consent(h)
    await h.press(MOM, "lang:set:uz", name="Мама")
    async with SessionLocal() as s:
        topic = await h.explain.start(s, kid_id, "kasrlar", source="web")
        for step, option in enumerate(CORRECT):
            await h.explain.answer(s, kid_id, topic.id, step, option)
    await process_events_once(h.bot)
    text = h.api.last(MOM).text
    assert "«kasrlar» mavzusini yopdi" in text and "saytda" in text
