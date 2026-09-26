"""Stories для ученика (микро-обучение): короткие карточки по теме и мини-вопросы.

Откуда берутся:
- ученик сам просит тему — ИИ делает 6–10 карточек (≤ 20 слов), вопросы проверяются
  так же, как в «Объясни тему»: арифметика кодом, остальное вторым запросом. Тратит
  одну попытку из дневного лимита объяснений;
- учитель отправляет Stories из материалов урока по учебнику всем своим ученикам.

Награда — EduCoin (коины магазина персонажа): за просмотр до конца и за каждый ответ,
верный с первой попытки. Выдаётся один раз.
"""
from __future__ import annotations

import logging

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import local_today, utcnow
from app.db.models import LessonMaterial, Student, StoryDeck, StoryView, User
from app.repositories import usage as usage_repo
from app.repositories.students import get_student
from app.services.explain import MAX_TITLE_LENGTH, ExplainService
from app.services.gamification import mark_active
from app.services.journal import linked_students

log = logging.getLogger(__name__)

COINS_FOR_STORY = 2  # за просмотр до конца
COINS_PER_ANSWER = 1  # за каждый ответ, верный с первой попытки


class StoryError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


def question_slides(slides: list[dict]) -> list[int]:
    return [i for i, s in enumerate(slides) if s.get("question")]


def _items(slides: list[dict]) -> list[dict]:
    """Вопросы Stories в формате проверки ответов (как шаги объяснения)."""
    return [
        {"question": s["question"], "options": s["options"], "correct": s["correct"], "context": f"{s['title']}. {s['text']}"}
        for s in slides
        if s.get("question")
    ]


# ---------- Stories ученика по его теме ----------

async def create_own(
    session: AsyncSession,
    explain: ExplainService,
    user: User,
    title: str,
    *,
    subject: str | None = None,
    grade: int | None = None,
) -> StoryView:
    title = title.strip()
    if not title:
        raise StoryError("need_topic", 422)
    if len(title) > MAX_TITLE_LENGTH:
        raise StoryError("topic_too_long", 422)
    await explain.ensure_can_start(session, user.id)  # ученик, согласие, лимит
    today = local_today()
    if not await usage_repo.try_reserve(session, user.id, today, explain.settings.daily_explain_limit):
        raise StoryError("limit_reached", 429)
    await session.commit()  # резерв — до долгого запроса к модели

    async def generate() -> list[dict]:
        return await explain.lesson.make_stories(title, subject=subject, grade=grade, lang=user.lang)

    try:
        slides = await explain._generate_checked(generate, _items)
    except Exception as exc:
        log.warning("Stories не получены: %s", exc)
        await usage_repo.refund(session, user.id, today)
        await session.commit()
        raise StoryError("generation_failed", 502) from exc

    deck = StoryDeck(author_user_id=user.id, title=title[:255], subject=subject, lang=user.lang, slides=slides)
    session.add(deck)
    await session.flush()
    view = StoryView(deck_id=deck.id, student_id=user.id, answers={})
    session.add(view)
    await mark_active(session, await get_student(session, user.id), today)
    await session.commit()
    return view


# ---------- Stories от учителя ----------

def _from_material(slides: list[dict]) -> list[dict]:
    out = []
    for s in slides:
        item = {"emoji": "", "title": s["title"], "text": s["text"]}
        if s.get("question") and s.get("options") and isinstance(s.get("correct"), int):
            item.update(question=s["question"], options=list(s["options"]), correct=s["correct"], explanation="")
        out.append(item)
    return out


async def send_from_material(session: AsyncSession, teacher: User, material: LessonMaterial) -> int:
    """Stories из материалов урока — всем привязанным ученикам учителя. Повторная отправка
    обновляет карточки и добавляет новых учеников; сколько учеников получили впервые."""
    slides = _from_material((material.content or {}).get("stories") or [])
    if not slides:
        raise StoryError("no_stories", 422)
    deck = await session.scalar(
        select(StoryDeck).where(StoryDeck.material_id == material.id, StoryDeck.author_user_id == teacher.id)
    )
    if deck is None:
        deck = StoryDeck(author_user_id=teacher.id, material_id=material.id, title=material.topic, lang=material.lang, slides=slides)
        session.add(deck)
        await session.flush()
    else:
        deck.title, deck.slides = material.topic, slides
    have = set(await session.scalars(select(StoryView.student_id).where(StoryView.deck_id == deck.id)))
    sent = 0
    for student, _user in await linked_students(session, teacher):
        if student.user_id not in have:
            session.add(StoryView(deck_id=deck.id, student_id=student.user_id, answers={}))
            sent += 1
    await session.commit()
    return sent


# ---------- Лента и просмотр ----------

async def feed(session: AsyncSession, student_id: int, limit: int = 50) -> list[tuple[StoryView, StoryDeck, User]]:
    """Сначала непросмотренные, внутри — новые сверху."""
    rows = await session.execute(
        select(StoryView, StoryDeck, User)
        .join(StoryDeck, StoryDeck.id == StoryView.deck_id)
        .join(User, User.id == StoryDeck.author_user_id)
        .where(StoryView.student_id == student_id)
        .order_by(StoryView.status.desc(), desc(StoryView.created_at), desc(StoryView.id))  # new > done
        .limit(limit)
    )
    return [tuple(r) for r in rows.all()]


async def get_owned(session: AsyncSession, student_id: int, view_id: int) -> tuple[StoryView, StoryDeck]:
    view = await session.get(StoryView, view_id)
    if view is None or view.student_id != student_id:
        raise StoryError("story_not_found", 404)  # чужие Stories не отличаем от несуществующих
    return view, await session.get(StoryDeck, view.deck_id)


def public_slides(view: StoryView, deck: StoryDeck) -> list[dict]:
    """Карточки без правильных ответов — их ученик узнаёт, только ответив."""
    answers = view.answers or {}
    out = []
    for i, slide in enumerate(deck.slides):
        item = {k: slide[k] for k in ("emoji", "title", "text")}
        if slide.get("question"):
            item.update(question=slide["question"], options=slide["options"])
            if str(i) in answers:
                item.update(answered=True, correct=slide["correct"], explanation=slide.get("explanation", ""))
        out.append(item)
    return out


async def answer(session: AsyncSession, student_id: int, view_id: int, slide: int, option: int) -> dict:
    view, deck = await get_owned(session, student_id, view_id)
    if not 0 <= slide < len(deck.slides) or not deck.slides[slide].get("question"):
        raise StoryError("bad_slide", 422)
    card = deck.slides[slide]
    if not 0 <= option < len(card["options"]):
        raise StoryError("bad_option", 422)
    right = option == card["correct"]
    if str(slide) not in (view.answers or {}):  # засчитываем только первую попытку
        view.answers = {**(view.answers or {}), str(slide): right}
        await session.commit()
    return {"right": right, "correct": card["correct"], "explanation": card.get("explanation", "")}


async def complete(session: AsyncSession, student: Student, view_id: int) -> dict:
    """Досмотрел до конца: EduCoin один раз. Все вопросы должны быть отвечены."""
    view, deck = await get_owned(session, student.user_id, view_id)
    answers = view.answers or {}
    if any(str(i) not in answers for i in question_slides(deck.slides)):
        raise StoryError("story_unanswered", 409)
    first_try = sum(1 for ok in answers.values() if ok)
    coins = COINS_FOR_STORY + COINS_PER_ANSWER * first_try
    # Атомарно: двойное нажатие / два устройства не дадут коины дважды
    done = await session.execute(
        update(StoryView)
        .where(StoryView.id == view.id, StoryView.status == "new")
        .values(status="done", coins=coins, completed_at=utcnow())
    )
    if done.rowcount:
        await session.execute(
            update(Student).where(Student.user_id == student.user_id).values(coins=Student.coins + coins)
        )
        await mark_active(session, student, local_today())
        await session.commit()
        await session.refresh(view)
    await session.refresh(student)
    return {
        "coins": view.coins,
        "awarded": bool(done.rowcount),
        "first_try": first_try,
        "questions": len(question_slides(deck.slides)),
        "total_coins": student.coins,
    }
