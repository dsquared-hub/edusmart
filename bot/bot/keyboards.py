"""Inline-клавиатуры бота."""
from __future__ import annotations

from urllib.parse import urlsplit

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.config import get_settings
from app.core.i18n import t
from app.db.models import Topic
from app.services.registration import GRADES


def _site_url(path: str = "") -> str | None:
    """Mini App-кнопки Telegram принимает только с HTTPS."""
    settings = get_settings()
    if not settings.web_app_enabled:
        return None
    return settings.web_url.rstrip("/") + path


LANGUAGES = (("ru", "🇷🇺 Русский"), ("uz", "🇺🇿 Oʻzbekcha"), ("en", "🇬🇧 English"))


def language_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for code, name in LANGUAGES:
        kb.button(text=name, callback_data=f"lang:set:{code}")
    kb.adjust(1)
    return kb.as_markup()


def role_keyboard() -> InlineKeyboardMarkup:
    """Бот — для взрослых; ученик — только в старом режиме BOT_STUDENT_LESSONS=1."""
    kb = InlineKeyboardBuilder()
    kb.button(text=t("role_parent"), callback_data="role:parent")
    kb.button(text=t("role_teacher"), callback_data="role:teacher")
    if get_settings().bot_student_lessons:
        kb.button(text=t("role_student"), callback_data="role:student")
    kb.button(text=t("btn_language"), callback_data="lang:menu")
    kb.adjust(1)
    return kb.as_markup()


def app_url() -> str:
    return get_settings().web_url.rstrip("/") + "/"


def student_app_keyboard() -> InlineKeyboardMarkup:
    """Ученик в боте: открыть приложение (Mini App по HTTPS, иначе обычная ссылка)."""
    kb = InlineKeyboardBuilder()
    site = _site_url("/")
    if site:
        kb.button(text=t("btn_open_app"), web_app=WebAppInfo(url=site))
    elif _public_url(app_url()):
        kb.button(text=t("btn_open_app"), url=app_url())
    kb.button(text=t("btn_language"), callback_data="lang:menu")
    kb.adjust(1)
    return kb.as_markup()


# ---------- Регистрация взрослого и ребёнка ----------

def keep_name_keyboard(name: str | None) -> InlineKeyboardMarkup | None:
    if not name:
        return None
    kb = InlineKeyboardBuilder()
    kb.button(text=t("btn_reg_keep_name", name=name[:40]), callback_data="reg:keepname")
    return kb.as_markup()


def share_phone_keyboard() -> ReplyKeyboardMarkup:
    """Номер берём только кнопкой Telegram — так он точно принадлежит пользователю."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_reg_share_phone"), request_contact=True)],
            [KeyboardButton(text=t("btn_reg_skip"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def after_registration_keyboard(role: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t("btn_reg_child" if role == "parent" else "btn_reg_student"), callback_data="reg:child")
    kb.button(text=t("btn_bind_child" if role == "parent" else "btn_bind_student"), callback_data=f"{role}:bind")
    kb.button(text=t("btn_later"), callback_data="reg:menu")
    kb.adjust(1)
    return kb.as_markup()


def grade_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for grade in GRADES:
        kb.button(text=str(grade), callback_data=f"reg:grade:{grade}")
    kb.button(text=t("btn_grade_skip"), callback_data="reg:grade:0")
    kb.button(text=t("btn_reg_cancel"), callback_data="reg:cancel")
    kb.adjust(len(GRADES), 1, 1)
    return kb.as_markup()


def child_consent_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    policy = _public_url(get_settings().policy_url)
    if policy:
        kb.button(text=t("btn_policy"), url=policy)
    kb.button(text=t("btn_reg_consent"), callback_data="reg:consent")
    kb.button(text=t("btn_reg_cancel"), callback_data="reg:cancel")
    kb.adjust(1)
    return kb.as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t("btn_reg_cancel"), callback_data="reg:cancel")
    return kb.as_markup()


def child_done_keyboard(role: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t("btn_reg_more_child" if role == "parent" else "btn_reg_more_student"), callback_data="reg:child")
    kb.button(text=t("btn_home_menu"), callback_data="reg:menu")
    kb.adjust(1)
    return kb.as_markup()


def student_menu_keyboard(resume: Topic | None = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if resume is not None:
        title = (resume.title or "")[:30]
        kb.button(text=t("btn_resume", title=title), callback_data=f"resume:{resume.id}")
    kb.button(text=t("btn_help"), callback_data="student:help")
    kb.button(text=t("btn_profile"), callback_data="student:profile")
    site = _site_url("/")
    if site:
        kb.button(text=t("btn_site"), web_app=WebAppInfo(url=site))
    kb.button(text=t("btn_language"), callback_data="lang:menu")
    kb.adjust(1)
    return kb.as_markup()


def resume_keyboard(topic: Topic) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=t("btn_resume", title=(topic.title or "")[:30]),
        callback_data=f"resume:{topic.id}",
    )
    return kb.as_markup()


def lesson_keyboard(topic_id: int) -> InlineKeyboardMarkup:
    """Под объяснением темы: перейти к вопросам."""
    kb = InlineKeyboardBuilder()
    kb.button(text=t("btn_to_questions"), callback_data=f"quiz:{topic_id}")
    kb.button(text=t("btn_cancel"), callback_data=f"pause:{topic_id}")
    kb.adjust(1)
    return kb.as_markup()


def step_keyboard(topic_id: int, step_index: int, options: list[str]) -> InlineKeyboardMarkup:
    """Варианты ответа. callback_data: ans:<тема>:<шаг>:<вариант> — шаг нужен,
    чтобы старая кнопка не засчиталась, если ученик ушёл дальше на сайте."""
    kb = InlineKeyboardBuilder()
    for index, option in enumerate(options):
        kb.button(text=option, callback_data=f"ans:{topic_id}:{step_index}:{index}")
    kb.button(text=t("btn_reread"), callback_data=f"lesson:{topic_id}")
    site = _site_url(f"/learn/{topic_id}")
    if site:
        kb.button(text=t("btn_open_on_site"), web_app=WebAppInfo(url=site))
    kb.button(text=t("btn_report"), callback_data=f"rep:{topic_id}:{step_index}")
    kb.button(text=t("btn_cancel"), callback_data=f"pause:{topic_id}")
    kb.adjust(1)
    return kb.as_markup()


def review_keyboard(topic_id: int, step_index: int) -> InlineKeyboardMarkup:
    """Под разбором ответа: следующий вопрос (или жалоба, если разбор неверный)."""
    kb = InlineKeyboardBuilder()
    kb.button(text=t("btn_next_question"), callback_data=f"quiz:{topic_id}")
    kb.button(text=t("btn_report"), callback_data=f"rep:{topic_id}:{step_index}")
    kb.adjust(1)
    return kb.as_markup()


def completed_keyboard(topic_id: int) -> InlineKeyboardMarkup | None:
    site = _site_url(f"/learn/{topic_id}")
    if not site:
        return None
    kb = InlineKeyboardBuilder()
    kb.button(text=t("btn_open_on_site"), web_app=WebAppInfo(url=site))
    return kb.as_markup()


def parent_menu_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t("btn_reg_child"), callback_data="reg:child")
    kb.button(text=t("btn_bind_child"), callback_data="parent:bind")
    kb.button(text=t("btn_consent"), callback_data="parent:consent")
    kb.button(text=t("btn_journal"), callback_data="journal:all")
    kb.button(text=t("btn_profile"), callback_data="parent:profile")
    kb.button(text=t("btn_support"), callback_data="support:new")
    kb.button(text=t("btn_language"), callback_data="lang:menu")
    kb.adjust(1)
    return kb.as_markup()


def teacher_menu_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t("btn_reg_student"), callback_data="reg:child")
    kb.button(text=t("btn_bind_student"), callback_data="teacher:bind")
    kb.button(text=t("btn_class"), callback_data="teacher:class")
    kb.button(text=t("btn_journal"), callback_data="journal:all")
    kb.button(text=t("btn_support"), callback_data="support:new")
    kb.button(text=t("btn_language"), callback_data="lang:menu")
    kb.adjust(1)
    return kb.as_markup()


def journal_keyboard(
    students: list[tuple[int, str]], *, back: bool = False
) -> InlineKeyboardMarkup | None:
    """Под журналом: фильтр по ученику, «весь журнал» и полный журнал на сайте."""
    kb = InlineKeyboardBuilder()
    for student_id, name in students[:20]:
        kb.button(text=f"👤 {name[:24]}", callback_data=f"journal:{student_id}")
    if back:
        kb.button(text=t("btn_journal_all"), callback_data="journal:all")
    site = _site_url("/journal")
    if site:
        kb.button(text=t("btn_journal_site"), web_app=WebAppInfo(url=site))
    if not list(kb.buttons):
        return None
    kb.adjust(2 if len(students) > 3 else 1)
    return kb.as_markup()


def evening_keyboard() -> InlineKeyboardMarkup | None:
    """Под напоминанием: открыть вечерний тест на сайте (Mini App)."""
    site = _site_url("/evening")
    if not site:
        return None
    kb = InlineKeyboardBuilder()
    kb.button(text=t("btn_evening"), web_app=WebAppInfo(url=site))
    return kb.as_markup()


def check_keyboard(check_id: int) -> InlineKeyboardMarkup | None:
    """Под уведомлением «проверка готова»: открыть очередь проверки на сайте."""
    site = _site_url(f"/teacher/checks/{check_id}")
    if not site:
        return None
    kb = InlineKeyboardBuilder()
    kb.button(text=t("btn_open_check"), web_app=WebAppInfo(url=site))
    return kb.as_markup()


def support_cancel_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t("btn_support_cancel"), callback_data="support:cancel")
    return kb.as_markup()


def support_reply_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t("btn_support_reply", id=ticket_id), callback_data=f"sup:reply:{ticket_id}")
    return kb.as_markup()


def web_login_keyboard(request_id: int, choices: list[int]) -> InlineKeyboardMarkup:
    """Вход на сайт: числа (одно совпадает с показанным на сайте) и «Это не я»."""
    kb = InlineKeyboardBuilder()
    for number in choices:
        kb.button(text=str(number), callback_data=f"wl:{request_id}:{number}")
    kb.button(text=t("btn_weblogin_not_me"), callback_data=f"wl:{request_id}:x")
    kb.adjust(len(choices), 1)
    return kb.as_markup()


def _public_url(url: str) -> str | None:
    """URL-кнопки Telegram не принимает ссылки на localhost — иначе всё сообщение
    падает с «Wrong HTTP URL» и кнопка согласия не доходит до родителя."""
    host = urlsplit(url).hostname or ""
    if host in ("localhost", "0.0.0.0") or host.startswith("127.") or "." not in host:
        return None
    return url


def policy_consent_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    policy = _public_url(get_settings().policy_url)
    if policy:
        kb.button(text=t("btn_policy"), url=policy)
    kb.button(text=t("consent_button"), callback_data="consent:confirm")
    kb.adjust(1)
    return kb.as_markup()


def new_code_keyboard(students: list[tuple[int, str]]) -> InlineKeyboardMarkup | None:
    """Кнопки «Новый код» для учеников со входом без Telegram."""
    if not students:
        return None
    kb = InlineKeyboardBuilder()
    for student_id, name in students:
        kb.button(text=t("btn_new_code", name=name[:24]), callback_data=f"newcode:{student_id}")
    kb.adjust(1)
    return kb.as_markup()


def children_keyboard(
    with_login: list[tuple[int, str]], children: list[tuple[int, str]]
) -> InlineKeyboardMarkup | None:
    """Профиль родителя: «Новый код» (для входа без Telegram) и «Удалить данные»."""
    if not with_login and not children:
        return None
    kb = InlineKeyboardBuilder()
    for student_id, name in with_login:
        kb.button(text=t("btn_new_code", name=name[:24]), callback_data=f"newcode:{student_id}")
    for student_id, name in children:
        kb.button(text=t("btn_delete_child", name=name[:24]), callback_data=f"delchild:{student_id}")
    kb.adjust(1)
    return kb.as_markup()


def delete_confirm_keyboard(student_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t("btn_delete_yes"), callback_data=f"delchild:yes:{student_id}")
    kb.button(text=t("btn_delete_no"), callback_data="delchild:no")
    kb.adjust(1)
    return kb.as_markup()


def resolve_keyboard(report_ids: list[int]) -> InlineKeyboardMarkup | None:
    if not report_ids:
        return None
    kb = InlineKeyboardBuilder()
    for report_id in report_ids:
        kb.button(text=t("btn_resolve", id=report_id), callback_data=f"resolve:{report_id}")
    kb.adjust(2)
    return kb.as_markup()