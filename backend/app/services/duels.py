"""PvP-дуэли (Dev-Spec, блок 1): два ученика отвечают на одни и те же 5 вопросов.

Асинхронно: соперникам не нужно быть онлайн одновременно. Создатель выбирает тему — ИИ
делает вопросы (каждый ответ перепроверен вторым запросом, генератор вечернего теста),
создание тратит одну попытку из дневного лимита объяснений. Позвать можно по коду /
ссылке (свой код дуэли, НЕ семейный код) или открытым вызовом — его берёт случайный
соперник того же класса.

Честность: вопросы выдаются по одному, время ответа засекает сервер (не больше
ANSWER_SECONDS — дольше засчитывается как неверный), верные ответы видны только когда
сыграли оба. Победа — больше верных, при равенстве — меньше суммарное время.
EduCoin: победа +5, ничья +2 каждому, участие +1. Вызов живёт EXPIRES.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import local_today, utcnow
from app.db.models import Duel, Student, User
from app.repositories import events as events_repo
from app.repositories import usage as usage_repo
from app.services.explain import MAX_TITLE_LENGTH, ExplainService
from app.services.gamification import mark_active
from app.services.gemini import SUBJECTS
from app.services.questions import QuestionGenerator

log = logging.getLogger(__name__)

QUESTIONS = 5
ANSWER_SECONDS = 30
EXPIRES = timedelta(hours=48)
COINS_WIN, COINS_DRAW, COINS_PLAYED = 5, 2, 1
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # без похожих 0/O, 1/I
EVENT_DUEL_FINISHED = "duel_finished"


class DuelError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


def _code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


async def create(
    session: AsyncSession,
    explain: ExplainService,
    generator: QuestionGenerator,
    user: User,
    student: Student,
    topic: str,
    subject: str | None,
    public: bool,
) -> Duel:
    topic = topic.strip()
    if not topic:
        raise DuelError("need_topic", 422)
    if len(topic) > MAX_TITLE_LENGTH:
        raise DuelError("topic_too_long", 422)
    if subject is not None and subject not in SUBJECTS:
        raise DuelError("bad_subject", 422)
    await explain.ensure_can_start(session, user.id)  # согласие и лимит
    today = local_today()
    if not await usage_repo.try_reserve(session, user.id, today, explain.settings.daily_explain_limit):
        raise DuelError("limit_reached", 429)
    await session.commit()
    try:
        items = await generator.generate(
            topic, SUBJECTS.get(subject or "other", "любой предмет"), student.grade or 7, 2, user.lang, count=QUESTIONS + 2
        )
    except Exception as exc:
        items = []
        log.warning("Дуэль: вопросы не получены: %s", exc)
    if len(items) < QUESTIONS:
        await usage_repo.refund(session, user.id, today)
        await session.commit()
        raise DuelError("generation_failed", 502)
    duel = Duel(
        code=_code(),
        creator_id=user.id,
        topic=topic[:255],
        subject=subject,
        grade=student.grade,
        lang=user.lang,
        public=public,
        questions=items[:QUESTIONS],
        results={str(user.id): _empty()},
        expires_at=utcnow() + EXPIRES,
    )
    session.add(duel)
    await session.commit()
    return duel


def _empty() -> dict:
    return {"answers": [], "shown_at": None, "done": False}


def _players(duel: Duel) -> list[int]:
    return [p for p in (duel.creator_id, duel.opponent_id) if p is not None]


async def get_for(session: AsyncSession, student_id: int, duel_id: int) -> Duel:
    duel = await session.get(Duel, duel_id)
    if duel is None or student_id not in _players(duel):
        raise DuelError("duel_not_found", 404)  # чужая дуэль неотличима от несуществующей
    return duel


async def join(session: AsyncSession, student: Student, code: str) -> Duel:
    duel = await session.scalar(select(Duel).where(Duel.code == code.strip().upper()))
    if duel is None:
        raise DuelError("duel_not_found", 404)
    if student.user_id in _players(duel):
        return duel  # своя или уже принятая — просто открываем
    return await _take(session, duel, student)


async def random_opponent(session: AsyncSession, student: Student) -> Duel:
    """Открытый вызов того же класса (не свой, не просроченный) — самый старый."""
    stmt = select(Duel).where(
        Duel.public.is_(True),
        Duel.status == "open",
        Duel.opponent_id.is_(None),
        Duel.creator_id != student.user_id,
        Duel.expires_at > utcnow(),
    )
    if student.grade is not None:
        stmt = stmt.where(or_(Duel.grade.is_(None), Duel.grade == student.grade))
    duel = await session.scalar(stmt.order_by(Duel.created_at))
    if duel is None:
        raise DuelError("no_open_duels", 404)
    return await _take(session, duel, student)


async def _take(session: AsyncSession, duel: Duel, student: Student) -> Duel:
    if duel.expires_at <= utcnow():
        raise DuelError("duel_expired", 410)
    # Условный UPDATE: два ученика не займут одну дуэль одновременно
    taken = await session.execute(
        update(Duel)
        .where(Duel.id == duel.id, Duel.opponent_id.is_(None))
        .values(opponent_id=student.user_id, status="active", results={**duel.results, str(student.user_id): _empty()})
        .execution_options(synchronize_session=False)
    )
    if not taken.rowcount:
        raise DuelError("duel_taken", 409)
    await session.commit()
    await session.refresh(duel)
    return duel


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


async def next_question(session: AsyncSession, student_id: int, duel_id: int) -> dict | None:
    """Следующий вопрос игроку; время пошло. Уже показан — тот же вопрос (без сброса таймера)."""
    duel = await get_for(session, student_id, duel_id)
    if duel.status == "finished" or duel.expires_at <= utcnow():
        raise DuelError("duel_closed", 409)
    me = dict(duel.results.get(str(student_id)) or _empty())
    n = len(me["answers"])
    if n >= QUESTIONS:
        return None
    if me["shown_at"] is None:
        me["shown_at"] = utcnow().isoformat()
        duel.results = {**duel.results, str(student_id): me}
        await session.commit()
    q = duel.questions[n]
    elapsed = (utcnow() - _parse(me["shown_at"])).total_seconds()
    return {"n": n, "question": q["question"], "options": q["options"], "seconds_left": max(0, int(ANSWER_SECONDS - elapsed))}


async def answer(session: AsyncSession, student: Student, duel_id: int, n: int, option: int) -> dict:
    duel = await get_for(session, student.user_id, duel_id)
    if duel.status == "finished":
        raise DuelError("duel_closed", 409)
    me = dict(duel.results.get(str(student.user_id)) or _empty())
    if n != len(me["answers"]) or me["shown_at"] is None:
        raise DuelError("stale_question", 409)
    q = duel.questions[n]
    if not 0 <= option < len(q["options"]):
        raise DuelError("bad_option", 422)
    ms = int((utcnow() - _parse(me["shown_at"])).total_seconds() * 1000)
    ok = option == q["correct"] and ms <= ANSWER_SECONDS * 1000  # опоздал — не засчитываем
    me["answers"] = [*me["answers"], {"option": option, "ok": ok, "ms": min(ms, ANSWER_SECONDS * 1000)}]
    me["shown_at"] = None
    me["done"] = len(me["answers"]) >= QUESTIONS
    duel.results = {**duel.results, str(student.user_id): me}
    await mark_active(session, student, local_today())
    await session.commit()
    if me["done"]:
        await _maybe_finish(session, duel)
    return {"ok": ok, "done": me["done"]}


def score(result: dict) -> tuple[int, int]:
    answers = result.get("answers", [])
    return sum(a["ok"] for a in answers), sum(a["ms"] for a in answers)


async def _maybe_finish(session: AsyncSession, duel: Duel) -> None:
    await session.refresh(duel)
    if duel.opponent_id is None or not all(duel.results.get(str(p), {}).get("done") for p in _players(duel)):
        return
    a, b = duel.creator_id, duel.opponent_id
    (ca, ta), (cb, tb) = score(duel.results[str(a)]), score(duel.results[str(b)])
    winner = a if (ca, -ta) > (cb, -tb) else b if (cb, -tb) > (ca, -ta) else None
    done = await session.execute(
        update(Duel).where(Duel.id == duel.id, Duel.status != "finished")
        .values(status="finished", winner_id=winner, finished_at=utcnow())
    )
    if not done.rowcount:
        return  # второй игрок закончил одновременно — итог уже подведён
    rewards = {a: COINS_DRAW, b: COINS_DRAW} if winner is None else {winner: COINS_WIN, (b if winner == a else a): COINS_PLAYED}
    for player, coins in rewards.items():
        await session.execute(update(Student).where(Student.user_id == player).values(coins=Student.coins + coins))
    await events_repo.enqueue(session, EVENT_DUEL_FINISHED, {"duel_id": duel.id})
    await session.commit()


async def mine(session: AsyncSession, student_id: int, limit: int = 30) -> list[Duel]:
    rows = await session.scalars(
        select(Duel)
        .where(or_(Duel.creator_id == student_id, Duel.opponent_id == student_id))
        .order_by(Duel.created_at.desc(), Duel.id.desc())
        .limit(limit)
    )
    return list(rows)


def public_view(duel: Duel, me: int, names: dict[int, str]) -> dict:
    """Своё — всегда; соперника — счёт после его игры; верные ответы — только после конца дуэли."""
    finished = duel.status == "finished"
    other = duel.opponent_id if me == duel.creator_id else duel.creator_id
    mine_res = duel.results.get(str(me)) or _empty()
    their = duel.results.get(str(other)) if other else None
    reward = 0
    if finished:
        reward = COINS_DRAW if duel.winner_id is None else COINS_WIN if duel.winner_id == me else COINS_PLAYED
    out = {
        "id": duel.id,
        "code": duel.code if me == duel.creator_id else None,
        "topic": duel.topic,
        "subject": duel.subject,
        "status": "expired" if duel.status == "open" and duel.expires_at <= utcnow() else duel.status,
        "public": duel.public,
        "i_am_creator": me == duel.creator_id,
        "opponent": names.get(other) if other else None,
        "me": {"correct": score(mine_res)[0], "ms": score(mine_res)[1], "answered": len(mine_res["answers"]), "done": mine_res["done"]},
        "them": {"correct": score(their)[0], "ms": score(their)[1], "done": their["done"]} if their and their.get("done") else None,
        "total": QUESTIONS,
        "winner": None if not finished else ("draw" if duel.winner_id is None else "me" if duel.winner_id == me else "them"),
        "reward": reward,
        "expires_at": duel.expires_at.isoformat() + "Z",
        "created_at": duel.created_at.isoformat() + "Z",
    }
    if finished:
        out["review"] = [
            {**q, "mine": (mine_res["answers"][i]["option"] if i < len(mine_res["answers"]) else None)}
            for i, q in enumerate(duel.questions)
        ]
    return out
