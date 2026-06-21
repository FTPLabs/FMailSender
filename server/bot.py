"""
FMail Sender — Telegram Bot + FastAPI License Server v3.0.0
Минималистичный интерфейс: Личный кабинет, Купить, Скачать, Поддержка.
Поддержка: тикеты с диалогом, медиафайлы, голосовые, ответы обеих сторон.
"""
import asyncio
import hmac
import html
import logging
import os
import sys

# FIX H-3: sys.path настраивается ДО любых относительных импортов
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import jwt
import uvicorn
from core._version import APP_VERSION
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import BaseStorage, StorageKey
import json
from pathlib import Path


# ─── Logging (MUST be before JsonFileStorage which uses logger in __init__) ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("bot")


# ─── Persistent FSM Storage ──────────────────────────────────────────────────

class JsonFileStorage(BaseStorage):
    """Persistent FSM storage backed by a JSON file. Survives bot restarts."""

    def __init__(self, path: str = "fsm_storage.json"):
        self._path = Path(path)
        self._data: Dict[str, Any] = self._load()
        self._lock: asyncio.Lock = asyncio.Lock()  # FIX КРИТ-1: защита _data от race condition

    def _load(self) -> Dict[str, Any]:
        """M-2 FIX: пробуем .tmp при краше во время _dump_sync."""
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except Exception as _e:
                logger.warning("JsonFileStorage._load: ошибка чтения %s: %s", self._path, _e)
        # Восстановление из .tmp (остаётся при краше в _dump_sync)
        _tmp = self._path.with_suffix(".tmp")
        if _tmp.exists():
            try:
                _data = json.loads(_tmp.read_text(encoding="utf-8"))
                _tmp.replace(self._path)  # восстанавливаем основной файл
                return _data
            except Exception as _e:
                logger.warning("JsonFileStorage._load: ошибка восстановления из .tmp: %s", _e)
        return {}

    def _dump_sync(self, snapshot: dict) -> None:
        """Sync write — принимает snapshot, не трогает self._data из потока (thread-safe)."""
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    async def _dump(self) -> None:
        """Async dump — snapshot в event loop, запись в thread pool (FIX: устраняет data race)."""
        async with self._lock:
            snapshot = dict(self._data)
        await asyncio.to_thread(self._dump_sync, snapshot)

    def _key(self, key: StorageKey) -> str:
        return f"{key.chat_id}:{key.user_id}"

    async def set_state(self, key: StorageKey, state: Any = None) -> None:
        async with self._lock:
            k = self._key(key)
            if k not in self._data:
                self._data[k] = {}
            self._data[k]["state"] = state.state if hasattr(state, "state") else state
        await self._dump()

    async def get_state(self, key: StorageKey) -> Any:
        async with self._lock:
            return self._data.get(self._key(key), {}).get("state")

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        async with self._lock:
            k = self._key(key)
            if k not in self._data:
                self._data[k] = {}
            self._data[k]["data"] = data
        await self._dump()
    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        async with self._lock:
            return dict(self._data.get(self._key(key), {}).get("data", {}))

    async def close(self) -> None:
        await self._dump()


from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from fastapi import FastAPI, HTTPException, Header, Form, UploadFile, File as FastAPIFile
from pydantic import BaseModel

import database as db
from database import set_terms_accepted, get_terms_accepted, set_captcha_passed, get_all_passed_users
from config import ADMIN_IDS, MODERATOR_IDS, ADMIN_API_KEY, ADMIN_WEB_SECRET, API_HOST, API_PORT, BOT_TOKEN, JWT_SECRET, KEY_PREFIX, PLANS, DOWNLOAD_URL, CHANNEL_ID
from crypto_pay import crypto_client

# ─── Moderator in-memory cache ────────────────────────────────────────────────
# Совокупность: env MODERATOR_IDS + модераторы добавленные через бот (из БД)
_moderator_ids: set[int] = set(MODERATOR_IDS)

# ─── GitHub Release Auto-Fetch ───────────────────────────────────────────────

GITHUB_REPO = "FTPLabs/FMailSender"
_release_cache: dict = {}
_release_cache_ts: float = 0.0
_RELEASE_CACHE_TTL = 300  # 5 minutes

# FIX L-1: Lock инициализируется на уровне модуля — правильно и безопасно
_release_cache_lock: asyncio.Lock = asyncio.Lock()

# ─── Канал + CAPTCHA ─────────────────────────────────────────────────────────
# CHANNEL_ID теперь берётся из config.py (env var CHANNEL_ID)

_captcha_passed: set[int] = set()   # in-memory кеш успешно прошедших капчу
_terms_accepted: set[int] = set()   # in-memory кеш принявших условия и политику

_CAPTCHA_POOL: list[str] = [
    "🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼",
    "🐨", "🐯", "🦁", "🐮", "🐸", "🐵", "🐔", "🦆",
]

async def fetch_latest_release() -> dict:
    """Auto-fetch latest GitHub release info. Cached for 5 min."""
    global _release_cache, _release_cache_ts
    import time
    async with _release_cache_lock:
        if _release_cache and (time.time() - _release_cache_ts) < _RELEASE_CACHE_TTL:
            return _release_cache
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        assets = data.get("assets", [])
                        exe_asset = next(
                            (a for a in assets if a.get("name", "").endswith(".exe")), None
                        )
                        _release_cache = {
                            "tag": data.get("tag_name", ""),
                            "html_url": data.get("html_url", ""),
                            # FIX КРИТ-1: используем DOWNLOAD_URL из config/DB, НЕ GitHub URL
                            "download_url": DOWNLOAD_URL,
                            "vt_url": _extract_vt_url(data.get("body", "")),
                            "body": data.get("body", ""),
                        }
                        _release_cache_ts = time.time()
                        return _release_cache
        except Exception as e:
            logger.warning("GitHub release fetch failed: %s", e)
        return {"tag": "", "html_url": DOWNLOAD_URL, "download_url": DOWNLOAD_URL, "vt_url": "", "body": ""}


def _extract_vt_url(release_body: str) -> str:
    """Extract VirusTotal URL from release notes if present."""
    import re
    m = re.search(r'https://www\.virustotal\.com/[^\s)\]]+', release_body)
    return m.group(0) if m else ""

# logger уже инициализирован выше (ранняя инициализация для JsonFileStorage)

from aiogram.client.default import DefaultBotProperties
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=JsonFileStorage("fsm_storage.json"))


# ─── FSM States ────────────────────────────────────────────────────────────

class BuyFlow(StatesGroup):
    waiting_hwid    = State()
    waiting_payment = State()


class SupportFlow(StatesGroup):
    waiting_ticket_message = State()   # user creates ticket
    waiting_ticket_reply   = State()   # user replies to admin


class AdminFlow(StatesGroup):
    issue_plan        = State()
    issue_telegram_id = State()
    issue_hwid        = State()
    issue_note        = State()
    set_price_plan    = State()
    set_price_value   = State()
    revoke_key        = State()
    broadcast_text    = State()
    confirm_clear     = State()
    set_download_url  = State()

    upload_file       = State()
    ticket_reply      = State()   # admin replies to ticket
    add_moderator_id  = State()   # admin adds moderator by telegram ID


class ModeratorFlow(StatesGroup):
    """FSM состояния для модераторов — подмножество AdminFlow."""
    issue_plan        = State()
    issue_telegram_id = State()
    issue_hwid        = State()
    issue_note        = State()
    revoke_key        = State()
    ticket_reply      = State()


class CaptchaFlow(StatesGroup):
    """Состояния для emoji-капчи при первом запуске."""
    waiting = State()


# ─── Keyboards ──────────────────────────────────────────────────────────────

def kb_main(is_admin_user: bool = False, is_mod_user: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="👤 Личный кабинет", callback_data="menu_cabinet")],
        [
            InlineKeyboardButton(text="💳 Купить лицензию", callback_data="menu_buy"),
            InlineKeyboardButton(text="📥 Скачать", callback_data="menu_download"),
        ],
        [InlineKeyboardButton(text="🎫 Поддержка", callback_data="menu_support")],
        [
            InlineKeyboardButton(text="📜 Конфиденциальность", callback_data="show_privacy"),
            InlineKeyboardButton(text="📋 Оферта", callback_data="show_terms"),
        ],
    ]
    if is_admin_user:
        rows.append([InlineKeyboardButton(text="⚙️ Панель администратора", callback_data="admin_panel")])
    elif is_mod_user:
        rows.append([InlineKeyboardButton(text="🛡 Панель модератора", callback_data="mod_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_support() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать в ЛС @ftpdev_sup", url="https://t.me/ftpdev_sup")],
        [InlineKeyboardButton(text="🎫 Оставить тикет", callback_data="support_ticket")],
        [
            InlineKeyboardButton(text="📜 Конфиденциальность", callback_data="show_privacy"),
            InlineKeyboardButton(text="📋 Оферта", callback_data="show_terms"),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_main")],
    ])


def kb_doc_back(accepted: bool = True) -> InlineKeyboardMarkup:
    """Клавиатура «назад» для документов.
    Если пользователь ещё не принял условия — показывает кнопку «Принимаю».
    """
    rows = [
        [
            InlineKeyboardButton(text="📜 Конфиденциальность", callback_data="show_privacy"),
            InlineKeyboardButton(text="📋 Оферта", callback_data="show_terms"),
        ],
    ]
    if accepted:
        rows.append([InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu_main")])
    else:
        rows.append([InlineKeyboardButton(text="✅ Принимаю оба документа", callback_data="accept_terms")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_terms_gate() -> InlineKeyboardMarkup:
    """Клавиатура ворот принятия условий."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📜 Конфиденциальность", callback_data="show_privacy"),
            InlineKeyboardButton(text="📋 Оферта", callback_data="show_terms"),
        ],
        [InlineKeyboardButton(text="✅ Принимаю оба документа", callback_data="accept_terms")],
    ])


def kb_plans(prices: dict | None = None) -> InlineKeyboardMarkup:
    rows = []
    for plan_id, plan in PLANS.items():
        if plan.get("admin_only"):
            continue
        price_val = prices.get(plan_id, plan['price_usdt']) if prices else plan['price_usdt']
        rows.append([InlineKeyboardButton(
            text=f"{plan['name']} — ${price_val:.2f} USDT",
            callback_data=f"buy_plan:{plan_id}",
        )])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="menu_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_payment(pay_url: str, invoice_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Оплатить", url=pay_url)],
        [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_pay:{invoice_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="menu_main")],
    ])


def kb_back_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu_main")]
    ])


def kb_admin(maintenance: bool = False) -> InlineKeyboardMarkup:
      maint_text = "🔧 Техработы: ВКЛ ✅" if maintenance else "🔧 Техработы: ВЫКЛ ❌"
      return InlineKeyboardMarkup(inline_keyboard=[
          [InlineKeyboardButton(text=maint_text,                callback_data="admin_maintenance_toggle")],
          [InlineKeyboardButton(text="🎟 Выдать ключ",          callback_data="admin_issue")],
          [InlineKeyboardButton(text="📋 Все лицензии",          callback_data="admin_list")],
          [InlineKeyboardButton(text="📊 Статистика",            callback_data="admin_stats")],
          [InlineKeyboardButton(text="💲 Изменить цены",         callback_data="admin_prices")],
          [InlineKeyboardButton(text="🚫 Отозвать ключ",         callback_data="admin_revoke")],
          [InlineKeyboardButton(text="📢 Рассылка",              callback_data="admin_broadcast")],
          [InlineKeyboardButton(text="🎫 Тикеты поддержки",     callback_data="admin_tickets")],



          [InlineKeyboardButton(text="📤 Загрузить .exe на сервер", callback_data="admin_upload_file")],
          [InlineKeyboardButton(text="🗑 Удалить все ключи",     callback_data="admin_clear_keys")],
          [InlineKeyboardButton(text="👥 Управление модераторами", callback_data="manage_moderators")],
          [InlineKeyboardButton(text="◀️ Главное меню",          callback_data="menu_main")],
      ])

def kb_moderator() -> InlineKeyboardMarkup:
    """Панель модератора — ограниченный набор действий без опасных операций."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟 Выдать ключ",      callback_data="mod_issue")],
        [InlineKeyboardButton(text="📋 Все лицензии",      callback_data="mod_list")],
        [InlineKeyboardButton(text="📊 Статистика",        callback_data="mod_stats")],
        [InlineKeyboardButton(text="🚫 Отозвать ключ",     callback_data="mod_revoke")],
        [InlineKeyboardButton(text="🎫 Тикеты поддержки", callback_data="mod_tickets")],
        [InlineKeyboardButton(text="◀️ Главное меню",      callback_data="menu_main")],
    ])


def kb_back_mod() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Панель модератора", callback_data="mod_panel")]
    ])


def kb_admin_plans() -> InlineKeyboardMarkup:
    rows = []
    for plan_id, plan in PLANS.items():
        label = f"[ПРОБНЫЙ] {plan['name']}" if plan.get("admin_only") else plan["name"]
        rows.append([InlineKeyboardButton(text=label, callback_data=f"admin_plan:{plan_id}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_back_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin_panel")]
    ])


def kb_ticket_admin(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Ответить", callback_data=f"ticket_reply:{ticket_id}")],
        [InlineKeyboardButton(text="✅ Закрыть тикет", callback_data=f"ticket_close:{ticket_id}")],
    ])


def kb_ticket_user(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Ответить", callback_data=f"ticket_user_reply:{ticket_id}")],
    ])


def kb_captcha(emojis: list[str], correct: str) -> InlineKeyboardMarkup:
    """Клавиатура emoji-капчи: 6 кнопок в 2 ряда по 3."""
    rows = []
    for i in range(0, len(emojis), 3):
        row = [
            InlineKeyboardButton(
                text=e,
                callback_data=f"captcha:{'ok' if e == correct else 'fail'}:{e}",
            )
            for e in emojis[i : i + 3]
        ]
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_subscription(invite_url: str) -> InlineKeyboardMarkup:
    """Клавиатура для обязательной подписки на канал."""
    rows: list[list[InlineKeyboardButton]] = []
    if invite_url:
        rows.append([InlineKeyboardButton(text="📢 Вступить в канал", url=invite_url)])
    rows.append([InlineKeyboardButton(text="✅ Я вступил — проверить", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── CAPTCHA + Channel helpers ────────────────────────────────────────────────

import random as _random


def _gen_captcha() -> tuple[str, list[str]]:
    """Генерирует (правильный_смайлик, список_6_смайликов_в_перемешку)."""
    emojis = _random.sample(_CAPTCHA_POOL, 6)
    correct = _random.choice(emojis)
    return correct, emojis


async def _check_subscription(user_id: int) -> bool:
    """Проверяет подписку пользователя на обязательный канал."""
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator", "restricted")
    except Exception as e:
        logger.debug("check_subscription error for %d: %s", user_id, e)
        return False


async def _make_invite_link(user_id: int) -> str:
    """Создаёт одноразовую 24-часовую ссылку для конкретного пользователя."""
    from datetime import timedelta
    try:
        expire = datetime.now(timezone.utc) + timedelta(hours=24)
        link = await bot.create_chat_invite_link(
            CHANNEL_ID,
            name=f"user_{user_id}",
            expire_date=expire,
            member_limit=1,
            creates_join_request=False,
        )
        return link.invite_link
    except Exception as e:
        logger.warning("invite link failed for user %d: %s", user_id, e)
        return ""


def parse_utc_dt(s: str) -> datetime:
    """Единая функция парсинга UTC datetime-строк из БД (заменяет 5 дублей в bot.py)."""
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ─── Helpers ────────────────────────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def is_moderator(user_id: int) -> bool:
    """True если пользователь является модератором (но НЕ администратором)."""
    return user_id in _moderator_ids and user_id not in ADMIN_IDS


def is_admin_or_mod(user_id: int) -> bool:
    """True если пользователь — администратор ИЛИ модератор."""
    return user_id in ADMIN_IDS or user_id in _moderator_ids


def _verify_admin_key(key: str) -> bool:
    """Проверяет API-ключ для веб-панели администратора."""
    return bool(ADMIN_WEB_SECRET) and key == ADMIN_WEB_SECRET


def _get_active_license(licenses: list) -> Optional[dict]:
    now = datetime.now(timezone.utc)
    for lic in licenses:
        if not lic.get("is_active"):
            continue
        try:
            exp_str = lic.get("expires_at", "")
            exp_dt = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if now <= exp_dt:
                return lic
        except Exception as _e:
            logger.debug("Failed to parse license expiry: %s", _e)
    return None


async def send_or_edit(message_or_query, text: str, reply_markup=None, **kwargs):
    if isinstance(message_or_query, CallbackQuery):
        try:
            await message_or_query.message.edit_text(text, reply_markup=reply_markup, **kwargs)
        except Exception as _edit_err:
            logger.debug("edit_text failed (%s), falling back to answer", _edit_err)
            await message_or_query.message.answer(text, reply_markup=reply_markup, **kwargs)
        await message_or_query.answer()
    else:
        await message_or_query.answer(text, reply_markup=reply_markup, **kwargs)


def _extract_media(message: Message) -> tuple[str, str]:
    """Возвращает (file_id, file_type) из сообщения или ('', '')."""
    if message.photo:
        return message.photo[-1].file_id, "photo"
    if message.video:
        return message.video.file_id, "video"
    if message.voice:
        return message.voice.file_id, "voice"
    if message.audio:
        return message.audio.file_id, "audio"
    if message.document:
        return message.document.file_id, "document"
    if message.sticker:
        return message.sticker.file_id, "sticker"
    if message.video_note:
        return message.video_note.file_id, "video_note"
    if message.animation:
        return message.animation.file_id, "animation"
    return "", ""


async def _send_media(chat_id: int, file_id: str, file_type: str, caption: str = "", reply_markup=None):
    """Отправляет медиа-сообщение по типу."""
    kwargs = {"caption": caption, "reply_markup": reply_markup} if caption else {"reply_markup": reply_markup}
    if file_type == "photo":
        await bot.send_photo(chat_id, file_id, **{k: v for k, v in kwargs.items() if v is not None})
    elif file_type == "video":
        await bot.send_video(chat_id, file_id, **{k: v for k, v in kwargs.items() if v is not None})
    elif file_type == "voice":
        await bot.send_voice(chat_id, file_id, **{"reply_markup": reply_markup} if reply_markup else {})
    elif file_type == "audio":
        await bot.send_audio(chat_id, file_id, **{k: v for k, v in kwargs.items() if v is not None})
    elif file_type == "document":
        await bot.send_document(chat_id, file_id, **{k: v for k, v in kwargs.items() if v is not None})
    elif file_type == "sticker":
        await bot.send_sticker(chat_id, file_id, **{"reply_markup": reply_markup} if reply_markup else {})
    elif file_type == "video_note":
        await bot.send_video_note(chat_id, file_id, **{"reply_markup": reply_markup} if reply_markup else {})
    elif file_type == "animation":
        await bot.send_animation(chat_id, file_id, **{k: v for k, v in kwargs.items() if v is not None})
    else:
        if caption:
            await bot.send_message(chat_id, caption, reply_markup=reply_markup)


# ─── /start ─────────────────────────────────────────────────────────────────

_TERMS_GATE_TEXT = (
    "📋 <b>Условия использования</b>\n\n"
    "Перед началом ознакомься с документами:\n"
    "• <b>Политика конфиденциальности</b> — принцип полной анонимности, что мы храним и почему\n"
    "• <b>Публичная оферта</b> — условия лицензии, оплаты и запрещённые действия\n\n"
    "Нажми кнопки ниже чтобы прочитать, затем подтверди принятие."
)



async def _require_onboarding(query: CallbackQuery) -> bool:
    """FIX СРЕДН-1: проверяет прохождение onboarding для callback handlers."""
    user = query.from_user
    if user.id not in _captcha_passed:
        await query.answer("⚠️ Сначала пройди /start для верификации", show_alert=True)
        return False
    if not await _check_subscription(user.id):
        await query.answer("⚠️ Сначала вступи в канал (/start)", show_alert=True)
        return False
    if user.id not in _terms_accepted:
        await query.answer("⚠️ Сначала прими условия (/start)", show_alert=True)
        return False
    return True

async def _show_terms_gate(target, user) -> None:
    """Шаг 3 флоу: принятие политики конфиденциальности и оферты."""
    await send_or_edit(target, _TERMS_GATE_TEXT, reply_markup=kb_terms_gate())


async def _show_main_menu(target, user) -> None:
    """Показывает главное меню (используется после CAPTCHA и проверки подписки)."""
    text = (
        f"👋 Привет, <b>{user.first_name}</b>!\n\n"
        f"<b>FMail Sender</b> — профессиональный инструмент для email-рассылок.\n\n"
        f"Выбери действие:"
    )
    markup = kb_main(is_admin(user.id), is_mod_user=is_moderator(user.id))
    await send_or_edit(target, text, reply_markup=markup)


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = message.from_user
    try:
        await db.upsert_user(user.id, user.username or "", user.first_name or "")
    except Exception as e:
        logger.error("DB error in cmd_start: %s", e)

    # Шаг 1: emoji-капча — обязательна для ВСЕХ (включая админов)
    if user.id not in _captcha_passed:
        correct, emojis = _gen_captcha()
        await state.set_state(CaptchaFlow.waiting)
        await state.update_data(captcha_correct=correct)
        await message.answer(
            "🔒 <b>Проверка безопасности</b>\n\n"
            f"Найди и нажми на этот смайлик: <b>{correct}</b>",
            reply_markup=kb_captcha(emojis, correct),
        )
        return

    # Шаг 2: подписка на канал — обязательна для ВСЕХ
    if not await _check_subscription(user.id):
        invite = await _make_invite_link(user.id)
        await message.answer(
            "📢 <b>Обязательное условие доступа</b>\n\n"
            "Для использования бота необходимо вступить в наш канал.\n"
            "После вступления нажми кнопку <b>«Я вступил»</b>.",
            reply_markup=kb_subscription(invite),
        )
        return

    # Шаг 3: принятие условий — обязательно для ВСЕХ
    if user.id not in _terms_accepted:
        await _show_terms_gate(message, user)
        return

    await _show_main_menu(message, user)


@dp.callback_query(F.data.startswith("captcha:"), CaptchaFlow.waiting)
async def cb_captcha(query: CallbackQuery, state: FSMContext):
    """Обработчик ответа на emoji-капчу."""
    parts = query.data.split(":", 2)
    result = parts[1]  # "ok" или "fail"
    user = query.from_user

    if result == "ok":
        _captcha_passed.add(user.id)
        await set_captcha_passed(user.id)  # FIX: persist to DB
        await state.clear()
        await query.answer("✅ Верно!")

        # Шаг 2: после капчи — проверяем подписку на канал
        if not await _check_subscription(user.id):
            invite = await _make_invite_link(user.id)
            try:
                await query.message.edit_text(
                    "📢 <b>Обязательное условие доступа</b>\n\n"
                    "Для использования бота необходимо вступить в наш канал.\n"
                    "После вступления нажми кнопку <b>«Я вступил»</b>.",
                    reply_markup=kb_subscription(invite),
                )
            except Exception:
                await query.message.answer(
                    "📢 <b>Вступи в канал для доступа:</b>",
                    reply_markup=kb_subscription(invite),
                )
            return

        # Шаг 3: проверяем принятие условий
        if user.id not in _terms_accepted:
            await _show_terms_gate(query, user)
            return

        await _show_main_menu(query, user)
    else:
        await query.answer("❌ Неверно! Попробуй ещё раз.", show_alert=False)
        # Генерируем новую капчу
        correct, emojis = _gen_captcha()
        await state.update_data(captcha_correct=correct)
        try:
            await query.message.edit_text(
                "🔒 <b>Проверка безопасности</b>\n\n"
                f"Найди и нажми на этот смайлик: <b>{correct}</b>",
                reply_markup=kb_captcha(emojis, correct),
            )
        except Exception as _e:
            logger.warning("captcha_send: ошибка отправки сообщения: %s", _e)


@dp.callback_query(F.data == "check_sub")
async def cb_check_subscription(query: CallbackQuery):
    """Проверяет подписку пользователя на канал после нажатия кнопки."""
    user = query.from_user
    await query.answer("⏳ Проверяем подписку...")

    if not await _check_subscription(user.id):
        invite = await _make_invite_link(user.id)
        await query.answer("❌ Вы ещё не вступили в канал! Нажмите кнопку выше.", show_alert=True)
        try:
            await query.message.edit_reply_markup(reply_markup=kb_subscription(invite))
        except Exception as _e:
            logger.warning("check_subscription: не удалось обновить markup: %s", _e)
        return

    # Шаг 3: подписка есть — проверяем принятие условий
    if user.id not in _terms_accepted:
        await _show_terms_gate(query, user)
        return

    await _show_main_menu(query, user)


@dp.callback_query(F.data == "accept_terms")
async def cb_accept_terms(query: CallbackQuery, state: FSMContext):
    """Пользователь принял политику конфиденциальности и оферту."""
    user = query.from_user

    # Проверяем что предыдущие шаги тоже пройдены
    if user.id not in _captcha_passed:
        await query.answer("⚠️ Сначала пройди проверку безопасности. Напиши /start.", show_alert=True)
        return
    if not await _check_subscription(user.id):
        await query.answer("⚠️ Сначала вступи в канал.", show_alert=True)
        return

    _terms_accepted.add(user.id)
    await set_terms_accepted(user.id)  # FIX: persist to DB
    await query.answer("✅ Условия приняты! Добро пожаловать.")
    await state.clear()
    await _show_main_menu(query, user)


@dp.callback_query(F.data == "menu_main")
async def cb_menu_main(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await send_or_edit(query, "🏠 <b>Главное меню</b>", reply_markup=kb_main(is_admin(query.from_user.id), is_mod_user=is_moderator(query.from_user.id)))


# ─── Личный кабинет ─────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_cabinet")
async def cb_cabinet(query: CallbackQuery):
    user = query.from_user
    try:
        licenses = await db.get_license_by_telegram(user.id)
        hwid = await db.get_user_hwid(user.id)
    except Exception as e:
        logger.error("DB error in cb_cabinet: %s", e)
        await send_or_edit(query, "⚠️ Ошибка БД. Попробуй позже.", reply_markup=kb_back_main())
        return
    active_lic = _get_active_license(licenses)

    lines = [f"👤 <b>Личный кабинет</b>\n"]
    lines.append(f"🆔 ID: <code>{user.id}</code>")
    lines.append(f"💻 HWID: <code>{hwid or 'не привязан'}</code>")
    lines.append("")

    if active_lic:
        plan_name = PLANS.get(active_lic.get("plan", ""), {}).get("name", active_lic.get("plan", "—"))
        exp_str = active_lic.get("expires_at", "")
        try:
            exp_dt = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            days_left = max(0, (exp_dt - datetime.now(timezone.utc)).days)
            exp_display = exp_dt.strftime("%d.%m.%Y")
        except Exception:
            days_left = 0
            exp_display = exp_str[:10]

        lines.append(f"📦 Подписка: <b>{plan_name}</b>")
        lines.append(f"📅 Истекает: <b>{exp_display}</b> ({days_left} дн.)")
        lines.append(f"✅ Статус: <b>Активна</b>")
    else:
        lines.append("📦 Подписка: <b>нет активной</b>")
        lines.append("💡 Нажми «Купить лицензию» для покупки")

    # FIX: кнопка сброса HWID если привязан
    if hwid and active_lic:
        kb_cabinet = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Сбросить HWID (1 раз/30 дн.)", callback_data="cabinet_reset_hwid")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu_main")],
        ])
    else:
        kb_cabinet = kb_back_main()
    await send_or_edit(query, "\n".join(lines), reply_markup=kb_cabinet)


# ─── Скачать приложение ──────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_download")
async def cb_menu_download(query: CallbackQuery):
    user_id = query.from_user.id
    try:
        _maint = (await db.get_setting("maintenance_mode") or "0") == "1"
    except Exception:
        _maint = False
    if _maint:
        await send_or_edit(
            query,
            "⚙️ <b>Технические работы</b>\n\nСкачивание временно недоступно. Попробуйте позже.",
            reply_markup=kb_main(is_admin(query.from_user.id), is_mod_user=is_moderator(query.from_user.id)),
        )
        return
    try:
        licenses = await db.get_license_by_telegram(user_id)
    except Exception as e:
        logger.error("db error in cb_menu_download: %s", e)
        licenses = []
    active_lic = _get_active_license(licenses)

    if not active_lic:
        await send_or_edit(
            query,
            "❌ <b>Скачивание недоступно</b>\n\nУ тебя нет активной подписки.\nНажми «Купить лицензию» для получения доступа.",
            reply_markup=kb_main(is_admin(user_id), is_mod_user=is_moderator(user_id)),
        )
        return

    # Auto-fetch latest release info from GitHub (cached 5 min); manual override takes priority
    try:
        release = await fetch_latest_release()

        manual_dl  = await db.get_setting("download_url") or ""

        dl_url = manual_dl or DOWNLOAD_URL  # FIX: всегда fmail.shop, не GitHub

    except Exception as _fetch_err:
        logger.warning("Download info fetch error: %s", _fetch_err)
        dl_url = DOWNLOAD_URL  # FIX: убран дубликат

    _lic_key = active_lic.get("key", "")

    def _url_with_key(url: str, key: str) -> str:
        if not key or not url.startswith("http"):
            return url
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}key={key}"

    final_url = _url_with_key(dl_url, _lic_key)
    buttons = [
        [InlineKeyboardButton(text="📥 Скачать .exe", url=final_url)],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu_main")],
    ]

    plan = PLANS.get(active_lic.get("plan", ""), {})
    exp = active_lic.get("expires_at", "")[:10]
    await send_or_edit(
        query,
        f"📥 <b>Скачать FMail Sender</b>\n\n"
        f"✅ {plan.get('name', active_lic.get('plan', ''))} | до {exp}\n\n"
        f"Нажми кнопку ниже — файл <b>FMailSender.exe</b> скачается напрямую.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )




# ─── Сброс HWID (1 раз в 30 дней) ───────────────────────────────────────────

@dp.callback_query(F.data == "cabinet_reset_hwid")
async def cb_cabinet_reset_hwid(query: CallbackQuery):
    """FIX НОВЫЙ: показывает информацию о сбросе HWID и запрашивает подтверждение."""
    user_id = query.from_user.id
    try:
        reset_info = await db.get_hwid_reset_info(user_id)
    except Exception as e:
        logger.error("get_hwid_reset_info error: %s", e)
        await query.answer("⚠️ Ошибка БД. Попробуй позже.", show_alert=True)
        return

    if not reset_info.get("can_reset"):
        days_left = reset_info.get("days_left", 0)
        await query.answer(
            f"❌ Сброс HWID доступен 1 раз в 30 дней.\nСледующий сброс через {days_left} дн.",
            show_alert=True,
        )
        return

    kb_confirm = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, сбросить HWID", callback_data="confirm_reset_hwid")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="menu_cabinet")],
    ])
    await send_or_edit(
        query,
        "🔄 <b>Сброс HWID</b>\n\n"
        "После сброса лицензия <b>отвяжется от текущего компьютера</b>.\n"
        "При следующем запуске FMailSender HWID привяжется автоматически.\n\n"
        "⏰ Это действие доступно <b>1 раз в 30 дней</b>.\n\n"
        "Подтвердить сброс?",
        reply_markup=kb_confirm,
    )


@dp.callback_query(F.data == "confirm_reset_hwid")
async def cb_confirm_reset_hwid(query: CallbackQuery):
    """FIX НОВЫЙ: выполняет сброс HWID после подтверждения."""
    user_id = query.from_user.id
    try:
        success = await db.reset_user_hwid(user_id)
    except Exception as e:
        logger.error("reset_user_hwid error for %d: %s", user_id, e)
        await query.answer("⚠️ Ошибка при сбросе. Попробуй позже.", show_alert=True)
        return

    if not success:
        await query.answer("❌ Сброс HWID ещё не доступен (прошло менее 30 дней).", show_alert=True)
        return

    await send_or_edit(
        query,
        "✅ <b>HWID успешно сброшен!</b>\n\n"
        "Лицензия отвязана от старого компьютера.\n"
        "При следующем запуске FMailSender HWID привяжется автоматически.\n\n"
        "⏰ Следующий сброс будет доступен через <b>30 дней</b>.",
        reply_markup=kb_back_main(),
    )
    logger.info("User %d successfully reset HWID", user_id)

# ─── Юридические документы ───────────────────────────────────────────────────

_PRIVACY_TEXT = """📜 <b>ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ</b>
<i>FMailSender · Актуально с июня 2026</i>

<b>1. ПРИНЦИП ПОЛНОЙ АНОНИМНОСТИ</b>
Мы работаем по принципу минимального сбора данных. Мы <u>не требуем</u>:
— Реального имени или фамилии
— Email-адреса пользователя
— Номера телефона
— Адреса проживания или регистрации
— Паспортных или иных документов

<b>2. КАКИЕ ДАННЫЕ МЫ ХРАНИМ</b>
Для работы сервиса технически необходимы:
• <b>Telegram ID</b> — числовой идентификатор аккаунта
• <b>Username / имя</b> — для обращения в переписке
• <b>HWID-хэш</b> — SHA-256 отпечаток устройства (необратимый, не позволяет идентифицировать устройство или владельца)
• <b>История платежей</b> — только invoice ID от CryptoBot, без данных карт

<b>3. КАК ИСПОЛЬЗУЮТСЯ ДАННЫЕ</b>
Исключительно для:
• Привязки лицензии к устройству (HWID)
• Ответов на тикеты поддержки
• Проверки активности лицензии

<b>4. ПЛАТЕЖИ И АНОНИМНОСТЬ</b>
Оплата принимается <b>только криптовалютой</b> через CryptoBot. Мы не видим и не храним данные банковских карт. Все транзакции на уровне блокчейна анонимны.

<b>5. ТРЕТЬИ СТОРОНЫ</b>
Мы не продаём, не сдаём в аренду и не передаём ваши данные третьим лицам ни при каких условиях, включая запросы от организаций и частных лиц.

<b>6. ХРАНЕНИЕ И БЕЗОПАСНОСТЬ</b>
• База данных хранится на выделенном VPS-сервере с ограниченным доступом
• Токены и секретные ключи в логах не появляются
• Логи активности ваших email-рассылок на нашем сервере <b>не хранятся</b>

<b>7. ВАШИ ПРАВА</b>
Через поддержку (@ftpdev_sup) вы можете:
— Запросить полную копию ваших данных
— Потребовать удаление аккаунта и всех данных
— Отозвать лицензию досрочно

<b>8. КОНТАКТ</b>
По вопросам конфиденциальности: @ftpdev_sup"""

_TERMS_TEXT = """📋 <b>ПУБЛИЧНАЯ ОФЕРТА</b>
<i>FMailSender · Договор-оферта на использование ПО</i>

<b>1. ПРЕДМЕТ</b>
Разработчик предоставляет Пользователю неисключительную лицензию на программное обеспечение FMailSender для отправки email-рассылок. Покупка лицензии означает безоговорочное принятие всех условий данной оферты.

<b>2. ЛИЦЕНЗИЯ</b>
• Привязывается к HWID (аппаратному идентификатору) одного устройства
• Использование допускается только на том устройстве, с которого была активирована
• Передача, перепродажа или аренда лицензии третьим лицам <b>запрещена</b>
• Срок лицензии указан в тарифном плане на момент покупки

<b>3. ТАРИФЫ И ОПЛАТА</b>
• Оплата принимается <b>только криптовалютой</b> через CryptoBot
• Цены в USDT; актуальные тарифы в разделе «Купить лицензию»
• После успешной оплаты лицензия активируется автоматически
• Тарифы могут изменяться для <u>новых</u> покупок без уведомления

<b>4. ВОЗВРАТ СРЕДСТВ</b>
После активации лицензии возврат <b>не производится</b>. Криптовалютные платежи необратимы по своей природе. Исключение — доказанная техническая неисправность по вине разработчика (рассматривается индивидуально).

<b>5. ЗАПРЕЩЁННОЕ ИСПОЛЬЗОВАНИЕ</b>
Использование ПО запрещено для:
— Рассылок без явного согласия получателей (спам)
— Фишинга, мошенничества и социальной инженерии
— Действий, нарушающих законодательство страны пользователя
— Атак на почтовые серверы (флуд, перебор паролей)
— Обхода фильтров почтовых провайдеров в недобросовестных целях

<b>6. ОТВЕТСТВЕННОСТЬ</b>
ПО предоставляется «<i>как есть</i>» (as is). Разработчик не несёт ответственности за прямые или косвенные убытки от использования программы. Соответствие рассылок законодательству — ответственность Пользователя.

<b>7. ПОДДЕРЖКА</b>
• Через Telegram: @ftpdev_sup
• Через тикет-систему бота
• Время ответа — до 48 часов
• Баги по вине разработчика устраняются бесплатно и в приоритетном порядке

<b>8. ИЗМЕНЕНИЕ УСЛОВИЙ</b>
Разработчик вправе изменять условия с предварительным уведомлением. Продолжение использования ПО после изменений означает их принятие.

<b>9. АКЦЕПТ ОФЕРТЫ</b>
Оплата лицензии является полным и безоговорочным акцептом данной оферты.

<b>Контакт:</b> @ftpdev_sup"""


@dp.callback_query(F.data == "show_privacy")
async def cb_show_privacy(query: CallbackQuery, state: FSMContext):
    """Показывает политику конфиденциальности."""
    await state.clear()
    accepted = query.from_user.id in _terms_accepted
    await send_or_edit(query, _PRIVACY_TEXT, reply_markup=kb_doc_back(accepted=accepted))


@dp.callback_query(F.data == "show_terms")
async def cb_show_terms(query: CallbackQuery, state: FSMContext):
    """Показывает условия публичной оферты."""
    await state.clear()
    accepted = query.from_user.id in _terms_accepted
    await send_or_edit(query, _TERMS_TEXT, reply_markup=kb_doc_back(accepted=accepted))


# ─── Поддержка ───────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_support")
async def cb_support(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await send_or_edit(
        query,
        "🎫 <b>Поддержка</b>\n\nКак хочешь обратиться?",
        reply_markup=kb_support(),
    )


@dp.callback_query(F.data == "support_ticket")
async def cb_support_ticket(query: CallbackQuery, state: FSMContext):
    await state.set_state(SupportFlow.waiting_ticket_message)
    await send_or_edit(
        query,
        "🎫 <b>Новый тикет</b>\n\nОпиши проблему. Можно отправить текст, фото, видео, голосовое или документ:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="menu_support")]
        ]),
    )


@dp.message(SupportFlow.waiting_ticket_message)
async def msg_ticket_create(message: Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    text = message.text or message.caption or ""
    file_id, file_type = _extract_media(message)

    if not text and not file_id:
        await message.answer("❌ Отправь текст или медиафайл.")
        await state.set_state(SupportFlow.waiting_ticket_message)
        return

    try:
        hwid = await db.get_user_hwid(user.id)
        licenses = await db.get_license_by_telegram(user.id)
    except Exception as e:
        logger.error("DB error create ticket: %s", e)
        hwid = ""
        licenses = []
    active_lic = _get_active_license(licenses)
    plan_info = ""
    if active_lic:
        pn = PLANS.get(active_lic.get("plan", ""), {}).get("name", "—")
        plan_info = f" · {pn}"

    ticket_id = await db.create_ticket(user.id, user.username or "", user.first_name or "")
    await db.add_ticket_message(ticket_id, user.id, "user", text, file_id, file_type)

    mention = f"@{user.username}" if user.username else f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"
    header = (
        f"🎫 <b>Тикет #{ticket_id}</b>\n"
        f"👤 {mention} · <code>{user.id}</code>\n"
        f"💻 {hwid or '—'}{plan_info}\n\n"
    )
    body = html.escape(text) if text else "📎 медиафайл"
    admin_kb = kb_ticket_admin(ticket_id)

    _staff_ids = list(ADMIN_IDS) + [uid for uid in _moderator_ids if uid not in ADMIN_IDS]
    for staff_id in _staff_ids:
        try:
            if file_id:
                await _send_media(staff_id, file_id, file_type, caption=header + body, reply_markup=admin_kb)
            else:
                await bot.send_message(staff_id, header + body, reply_markup=admin_kb)
        except Exception as e:
            logger.warning("Cannot send ticket #%d to staff %d: %s", ticket_id, staff_id, e)

    await message.answer(
        f"✅ <b>Тикет #{ticket_id} создан</b>\n\nОтветим в этот чат. Обычно в течение нескольких часов.",
        reply_markup=kb_main(is_admin(user.id), is_mod_user=is_moderator(user.id)),
    )


# ─── Ответ пользователя на тикет ─────────────────────────────────────────────

@dp.callback_query(F.data.startswith("ticket_user_reply:"))
async def cb_ticket_user_reply(query: CallbackQuery, state: FSMContext):
    ticket_id = int(query.data.split(":", 1)[1])
    ticket = await db.get_ticket(ticket_id)
    if not ticket or ticket["status"] != "open":
        await query.answer("Тикет закрыт.", show_alert=True)
        return
    await state.set_state(SupportFlow.waiting_ticket_reply)
    await state.update_data(ticket_id=ticket_id)
    await query.message.answer(
        f"↩️ <b>Ответ на тикет #{ticket_id}</b>\n\nОтправь сообщение (текст, фото, голосовое…):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="menu_main")]
        ]),
    )
    await query.answer()


@dp.message(SupportFlow.waiting_ticket_reply)
async def msg_ticket_user_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    await state.clear()

    if not ticket_id:
        await message.answer("⚠️ Ошибка: тикет не найден.", reply_markup=kb_back_main())
        return

    ticket = await db.get_ticket(ticket_id)
    if not ticket or ticket["status"] != "open":
        await message.answer("ℹ️ Этот тикет уже закрыт.", reply_markup=kb_back_main())
        return

    user = message.from_user
    text = message.text or message.caption or ""
    file_id, file_type = _extract_media(message)

    await db.add_ticket_message(ticket_id, user.id, "user", text, file_id, file_type)

    header = f"↩️ <b>Тикет #{ticket_id}</b> — ответ клиента\n👤 {user.first_name}\n\n"
    body = html.escape(text) if text else "📎 медиафайл"
    admin_kb = kb_ticket_admin(ticket_id)

    _staff_ids = list(ADMIN_IDS) + [uid for uid in _moderator_ids if uid not in ADMIN_IDS]
    for staff_id in _staff_ids:
        try:
            if file_id:
                await _send_media(staff_id, file_id, file_type, caption=header + body, reply_markup=admin_kb)
            else:
                await bot.send_message(staff_id, header + body, reply_markup=admin_kb)
        except Exception as e:
            logger.warning("Cannot forward reply ticket #%d to staff %d: %s", ticket_id, staff_id, e)

    await message.answer("✅ Ответ отправлен.", reply_markup=kb_back_main())


# ─── Ответ администратора на тикет ───────────────────────────────────────────

@dp.callback_query(F.data.startswith("ticket_reply:"))
async def cb_ticket_reply_admin(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        await query.answer("Нет доступа.", show_alert=True)
        return
    ticket_id = int(query.data.split(":", 1)[1])
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await query.answer("Тикет не найден.", show_alert=True)
        return
    if ticket["status"] != "open":
        await query.answer("Тикет закрыт.", show_alert=True)
        return
    await state.set_state(AdminFlow.ticket_reply)
    await state.update_data(ticket_id=ticket_id, ticket_user_id=ticket["user_id"])
    await query.message.answer(
        f"✏️ <b>Ответ на тикет #{ticket_id}</b>\n👤 {ticket['first_name']}\n\nОтправь ответ (текст, фото, голосовое…):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_panel")]
        ]),
    )
    await query.answer()


@dp.message(AdminFlow.ticket_reply)
async def msg_ticket_reply_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    user_id = data.get("ticket_user_id")
    await state.clear()

    if not ticket_id or not user_id:
        await message.answer("⚠️ Ошибка: данные тикета не найдены.", reply_markup=kb_admin())
        return

    text = message.text or message.caption or ""
    file_id, file_type = _extract_media(message)

    await db.add_ticket_message(ticket_id, message.from_user.id, "admin", text, file_id, file_type)

    header = f"💬 <b>Ответ поддержки · Тикет #{ticket_id}</b>\n\n"
    body = html.escape(text) if text else "📎 медиафайл"
    user_kb = kb_ticket_user(ticket_id)

    try:
        if file_id:
            await _send_media(user_id, file_id, file_type, caption=header + body, reply_markup=user_kb)
        else:
            await bot.send_message(user_id, header + body, reply_markup=user_kb)
        await message.answer(f"✅ Ответ отправлен пользователю (тикет #{ticket_id}).", reply_markup=kb_admin())
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {e}", reply_markup=kb_admin())


# ─── Закрыть тикет ───────────────────────────────────────────────────────────

@dp.callback_query(F.data.startswith("ticket_close:"))
async def cb_ticket_close(query: CallbackQuery):
    if not is_admin_or_mod(query.from_user.id):
        await query.answer("Нет доступа.", show_alert=True)
        return
    ticket_id = int(query.data.split(":", 1)[1])
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await query.answer("Тикет не найден.", show_alert=True)
        return
    await db.close_ticket(ticket_id)
    user_id = ticket["user_id"]
    try:
        await bot.send_message(
            user_id,
            f"✅ <b>Тикет #{ticket_id} закрыт</b>\n\nЕсли вопрос остался — создай новый тикет.",
            reply_markup=kb_main(is_admin(user_id), is_mod_user=is_moderator(user_id)),
        )
    except Exception as _e:
        logger.warning("Failed to notify user about ticket close: %s", _e)
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔒 Тикет #{ticket_id} закрыт", callback_data="noop")]
    ]))
    await query.answer(f"Тикет #{ticket_id} закрыт.")


@dp.callback_query(F.data == "noop")
async def cb_noop(query: CallbackQuery):
    await query.answer()


# ─── Admin: Тикеты поддержки ─────────────────────────────────────────────────

@dp.callback_query(F.data == "admin_tickets")
async def cb_admin_tickets(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return
    tickets = await db.get_open_tickets(limit=15)
    if not tickets:
        await send_or_edit(query, "🎫 Открытых тикетов нет.", reply_markup=kb_back_admin())
        return
    rows = []
    for t in tickets:
        name = t.get("first_name", "")
        uname = f"@{t['username']}" if t.get("username") else f"ID:{t['user_id']}"
        rows.append([InlineKeyboardButton(
            text=f"#{t['id']} · {name} ({uname})",
            callback_data=f"ticket_view:{t['id']}",
        )])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")])
    await send_or_edit(
        query,
        f"🎫 <b>Открытые тикеты ({len(tickets)})</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@dp.callback_query(F.data.startswith("ticket_view:"))
async def cb_ticket_view(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return
    ticket_id = int(query.data.split(":", 1)[1])
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await query.answer("Тикет не найден.", show_alert=True)
        return
    msgs = await db.get_ticket_messages(ticket_id)
    lines = [f"🎫 <b>Тикет #{ticket_id}</b> · {ticket.get('first_name', '')} @{ticket.get('username', '')}"]
    lines.append(f"📅 {ticket['created_at'][:16].replace('T', ' ')}\n")
    for m in msgs[-10:]:
        role_icon = "👤" if m["role"] == "user" else "🛠"
        ts = m["created_at"][11:16]
        content = m.get("text") or f"[{m.get('file_type', 'файл')}]"
        lines.append(f"{role_icon} <i>{ts}</i>  {content}")
    await send_or_edit(query, "\n".join(lines), reply_markup=kb_ticket_admin(ticket_id))


# ─── Buy Flow ───────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_buy")
async def cb_menu_buy(query: CallbackQuery):
    try:
        _maint = (await db.get_setting("maintenance_mode") or "0") == "1"
    except Exception:
        _maint = False
    if _maint:
        await send_or_edit(
            query,
            "⚙️ <b>Технические работы</b>\n\nПокупка подписки временно недоступна. Попробуйте позже.",
            reply_markup=kb_main(is_admin(query.from_user.id), is_mod_user=is_moderator(query.from_user.id)),
        )
        return
    lines = ["💳 <b>Выбери тарифный план:</b>\n"]
    for plan_id, plan in PLANS.items():
        if plan.get("admin_only"):
            continue
        price = await db.get_plan_price(plan_id)
        lines.append(f"<b>{plan['name']}</b> — <b>${price:.2f} USDT</b>\n   {plan['description']}\n")
    _prices = {}
    for _pid in PLANS:
        if not PLANS[_pid].get("admin_only"):
            _prices[_pid] = await db.get_plan_price(_pid)
    await send_or_edit(query, "\n".join(lines), reply_markup=kb_plans(prices=_prices))


@dp.callback_query(F.data.startswith("buy_plan:"))
async def cb_buy_plan(query: CallbackQuery, state: FSMContext):
    try:
        _maint = (await db.get_setting("maintenance_mode") or "0") == "1"
    except Exception:
        _maint = False
    if _maint:
        await query.answer("⚙️ Покупка временно недоступна — ведутся технические работы.", show_alert=True)
        return
    plan_id = query.data.split(":", 1)[1]
    if plan_id not in PLANS:
        await query.answer("Неизвестный план", show_alert=True)
        return
    if PLANS[plan_id].get("admin_only"):
        await query.answer("Этот план выдаётся только администратором.", show_alert=True)
        return
    current_hwid = await db.get_user_hwid(query.from_user.id)
    await state.update_data(plan_id=plan_id, hwid_only=False)

    if current_hwid:
        await state.set_state(BuyFlow.waiting_hwid)
        plan = PLANS[plan_id]
        price = await db.get_plan_price(plan_id)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Использовать текущий", callback_data=f"use_hwid:{current_hwid}")],
            [InlineKeyboardButton(text="⏭ Пропустить (HWID привяжется при запуске)", callback_data=f"skip_hwid:{plan_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_buy")],
        ])
        await send_or_edit(
            query,
            f"📦 <b>{plan['name']}</b> — ${price:.2f} USDT\n\n"
            f"💻 Текущий HWID: <code>{current_hwid}</code>\n\n"
            f"Использовать этот HWID или отправь новый:",
            reply_markup=kb,
        )
    else:
        await state.set_state(BuyFlow.waiting_hwid)
        kb_hwid_skip = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить (HWID привяжется при запуске)", callback_data=f"skip_hwid:{plan_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_buy")],
        ])
        await send_or_edit(
            query,
            f"📦 <b>{PLANS[plan_id]['name']}</b>\n\n"
            "💻 <b>HWID</b> — уникальный ID вашего ПК.\n\n"
            "<b>Нет программы?</b> Нажмите «Пропустить» — HWID привяжется автоматически при первом запуске.\n"
            "<b>Уже установлена?</b> Скопируйте HWID с экрана активации и отправьте сюда:",
            reply_markup=kb_hwid_skip,
        )


@dp.callback_query(F.data.startswith("use_hwid:"))
async def cb_use_hwid(query: CallbackQuery, state: FSMContext):
    hwid = query.data.split(":", 1)[1]
    data = await state.get_data()
    await _proceed_to_payment(query, state, hwid, data.get("plan_id", "week"))


@dp.callback_query(F.data.startswith("skip_hwid:"))
async def cb_skip_hwid(query: CallbackQuery, state: FSMContext):
    """FIX НОВЫЙ: HWID пропущен при покупке — лицензия без HWID,
    автопривязка произойдёт при первом запуске приложения (/v1/activate)."""
    plan_id = query.data.split(":", 1)[1]
    if plan_id not in PLANS or PLANS[plan_id].get("admin_only"):
        await query.answer("Неизвестный план", show_alert=True)
        return
    await state.clear()
    await _proceed_to_payment(query, state, "", plan_id)


@dp.message(BuyFlow.waiting_hwid)
async def msg_hwid(message: Message, state: FSMContext):
    hwid = (message.text or "").strip().upper()
    data = await state.get_data()
    if len(hwid) < 8 or " " in hwid:
        await message.answer("❌ Неверный формат HWID. Скопируй его из программы.")
        return
    await db.set_user_hwid(message.from_user.id, hwid)
    await db.upsert_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "")
    if data.get("hwid_only"):
        await state.clear()
        await message.answer(
            f"✅ HWID сохранён: <code>{hwid}</code>",
            reply_markup=kb_main(is_admin(message.from_user.id), is_mod_user=is_moderator(message.from_user.id)),
        )
        return
    plan_id = data.get("plan_id", "week")
    await _proceed_to_payment(message, state, hwid, plan_id)


async def _proceed_to_payment(event, state: FSMContext, hwid: str, plan_id: str):
    plan = PLANS[plan_id]
    price = await db.get_plan_price(plan_id)
    user_id = event.from_user.id if hasattr(event, "from_user") else event.message.from_user.id
    try:
        invoice = await crypto_client.create_invoice(
            amount=price,
            asset="USDT",
            description=f"FMail Sender — {plan['name']}",
        )
        pay_url = invoice.get("pay_url", "")
        invoice_id = str(invoice.get("invoice_id", ""))
    except Exception as e:
        logger.error(f"CryptoPay error: {e}")
        err_text = f"❌ Ошибка создания платежа: {e}"
        if isinstance(event, CallbackQuery):
            await send_or_edit(event, err_text, reply_markup=kb_back_main())
        else:
            await event.answer(err_text, reply_markup=kb_back_main())
        await state.clear()
        return

    await db.save_payment(telegram_id=user_id, invoice_id=invoice_id, plan=plan_id, hwid=hwid, amount=price)
    await state.update_data(invoice_id=invoice_id, hwid=hwid)
    await state.set_state(BuyFlow.waiting_payment)
    text = (
        f"💳 <b>Оплата</b>\n\n"
        f"📦 Тариф: <b>{plan['name']}</b>\n"
        f"💰 Сумма: <b>${price:.2f} USDT</b>\n"
        f"💻 HWID: <code>{hwid}</code>\n\n"
        f"Нажми <b>«Оплатить»</b> и после оплаты нажми «Проверить»."
    )
    if isinstance(event, CallbackQuery):
        await send_or_edit(event, text, reply_markup=kb_payment(pay_url, invoice_id))
    else:
        await event.answer(text, reply_markup=kb_payment(pay_url, invoice_id))


@dp.callback_query(F.data.startswith("check_pay:"))
async def cb_check_pay(query: CallbackQuery, state: FSMContext):
    invoice_id = query.data.split(":", 1)[1]
    payment = await db.get_payment(invoice_id)
    if not payment:
        await query.answer("❌ Платёж не найден.", show_alert=True)
        return
    try:
        paid = await crypto_client.check_invoice(
            invoice_id,
            expected_amount=payment.get("amount"),
            expected_asset="USDT",
        )
    except Exception as e:
        await query.answer(f"Ошибка проверки: {e}", show_alert=True)
        return
    if not paid:
        await query.answer("⏳ Оплата ещё не поступила. Попробуй через минуту.", show_alert=True)
        return
    # Atomic + idempotent: если уже обработан — вернёт существующий ключ
    license_data = await db.create_license_for_payment(
        invoice_id=invoice_id,
        plan=payment.get("plan", ""),
        hwid=payment.get("hwid", ""),
        telegram_id=payment.get("telegram_id", 0),
    )
    await state.clear()
    text = (
        f"✅ <b>Оплата подтверждена!</b>\n\n"
        f"📦 Тариф: <b>{PLANS.get(payment['plan'], {}).get('name', payment['plan'])}</b>\n\n"
        f"🔑 <b>Ваш лицензионный ключ:</b>\n<code>{license_data['key']}</code>\n\n"
        f"Введите его в программе на экране активации.\n"
        f"💻 HWID: <code>{payment.get('hwid') or 'привязывается при первой активации'}</code>"
    )
    await send_or_edit(query, text, reply_markup=kb_main(is_admin(query.from_user.id), is_mod_user=is_moderator(query.from_user.id)))


# ─── Admin Panel ─────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "admin_panel")
async def cb_admin_panel(query: CallbackQuery, state: FSMContext):
      if not is_admin(query.from_user.id):
          return
      await state.clear()
      try:
          stats = await db.get_stats()
      except Exception as e:
          logger.error("Admin stats error: %s", e)
          stats = {"active": 0, "total": 0, "users": 0, "paid": 0, "open_tickets": 0}
      try:
          maintenance = (await db.get_setting("maintenance_mode") or "0") == "1"
      except Exception:
          maintenance = False
      tickets_note = f"\n🎫 Открытых тикетов: <b>{stats.get('open_tickets', 0)}</b>" if stats.get("open_tickets") else ""
      maint_note = "\n🔧 Режим техработ: <b>ВКЛЮЧЁН</b> — покупки и скачивание заблокированы." if maintenance else ""
      text = (
          f"⚙️ <b>Панель администратора</b>\n\n"
          f"✅ Активных лицензий: <b>{stats.get('active', 0)}</b>\n"
          f"📦 Всего лицензий: <b>{stats.get('total', 0)}</b>\n"
          f"👥 Пользователей: <b>{stats.get('users', 0)}</b>"
          f"{tickets_note}"
          f"{maint_note}"
      )
      await send_or_edit(query, text, reply_markup=kb_admin(maintenance))


  



@dp.callback_query(F.data == "admin_maintenance_toggle")
async def cb_admin_maintenance_toggle(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return
    try:
        current = (await db.get_setting("maintenance_mode") or "0") == "1"
        new_val = "0" if current else "1"
        await db.set_setting("maintenance_mode", new_val)
        maintenance = new_val == "1"
    except Exception as e:
        logger.error("maintenance toggle error: %s", e)
        await query.answer("Ошибка переключения режима", show_alert=True)
        return
    status = "ВКЛЮЧЁН" if maintenance else "ВЫКЛЮЧЕН"
    await query.answer(f"🔧 Режим техработ {status}", show_alert=True)
    # Обновляем панель
    try:
        stats = await db.get_stats()
    except Exception:
        stats = {"active": 0, "total": 0, "users": 0, "paid": 0, "open_tickets": 0}
    tickets_note = f"\n🎫 Открытых тикетов: <b>{stats.get('open_tickets', 0)}</b>" if stats.get("open_tickets") else ""
    maint_note = "\n🔧 Режим техработ: <b>ВКЛЮЧЁН</b> — покупки и скачивание заблокированы." if maintenance else ""
    text = (
        f"⚙️ <b>Панель администратора</b>\n\n"
        f"✅ Активных лицензий: <b>{stats.get('active', 0)}</b>\n"
        f"📦 Всего лицензий: <b>{stats.get('total', 0)}</b>\n"
        f"👥 Пользователей: <b>{stats.get('users', 0)}</b>"
        f"{tickets_note}"
        f"{maint_note}"
    )
    await send_or_edit(query, text, reply_markup=kb_admin(maintenance))


@dp.callback_query(F.data == "admin_list")
async def cb_admin_list(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return
    licenses = await db.get_all_licenses(limit=10)
    if not licenses:
        await send_or_edit(query, "📋 Лицензий пока нет.", reply_markup=kb_back_admin())
        return
    parts = [f"📋 <b>Последние {len(licenses)} лицензий:</b>\n"]
    for lic in licenses:
        plan_name = PLANS.get(lic.get("plan", ""), {}).get("name", lic.get("plan", "—"))
        exp = lic.get("expires_at", "")[:10]
        hwid = lic.get("hwid") or "—"
        status = "✅" if lic.get("is_active") else "❌"
        parts.append(f"{status} <code>{lic['key']}</code>\n   {plan_name} | до {exp} | HWID: {hwid}")
        parts.append("")
    await send_or_edit(query, "\n".join(parts), reply_markup=kb_back_admin())


@dp.callback_query(F.data == "admin_stats")
async def cb_admin_stats(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return
    stats = await db.get_stats()
    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"✅ Активных лицензий: <b>{stats.get('active', 0)}</b>\n"
        f"📦 Всего лицензий: <b>{stats.get('total', 0)}</b>\n"
        f"💳 Оплаченных заказов: <b>{stats.get('paid', 0)}</b>\n"
        f"👥 Пользователей: <b>{stats.get('users', 0)}</b>\n"
        f"💰 Выручка: <b>${stats.get('revenue_usdt', 0.0):.2f} USDT</b>\n"
        f"🎫 Открытых тикетов: <b>{stats.get('open_tickets', 0)}</b>"
    )
    await send_or_edit(query, text, reply_markup=kb_back_admin())


# ─── Admin Issue Flow ────────────────────────────────────────────────────────

@dp.callback_query(F.data == "admin_issue")
async def cb_admin_issue(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        return
    await state.set_state(AdminFlow.issue_plan)
    await send_or_edit(query, "🎟 <b>Выдача ключа</b>\n\nВыбери тарифный план:", reply_markup=kb_admin_plans())


@dp.callback_query(F.data.startswith("admin_plan:"), AdminFlow.issue_plan)
async def cb_admin_plan_selected(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        return
    plan_id = query.data.split(":", 1)[1]
    await state.update_data(plan_id=plan_id)
    await state.set_state(AdminFlow.issue_telegram_id)
    plan = PLANS.get(plan_id, {})
    await send_or_edit(
        query,
        f"🎟 Тариф: <b>{plan.get('name', plan_id)}</b>\n\n"
        f"Отправь Telegram ID получателя (числовой) или <code>-</code> пропустить:",
        reply_markup=kb_back_admin(),
    )


@dp.message(AdminFlow.issue_telegram_id)
async def msg_admin_telegram_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    telegram_id = 0
    if raw != "-":
        try:
            telegram_id = int(raw)
        except ValueError:
            await message.answer("❌ Telegram ID должен быть числом или <code>-</code>")
            return
    await state.update_data(telegram_id=telegram_id)
    await state.set_state(AdminFlow.issue_hwid)
    await message.answer("💻 Отправь HWID получателя или <code>-</code> пропустить:", reply_markup=kb_back_admin())


@dp.message(AdminFlow.issue_hwid)
async def msg_admin_hwid(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    hwid = "" if raw == "-" else raw.upper()
    await state.update_data(hwid=hwid)
    await state.set_state(AdminFlow.issue_note)
    await message.answer("📝 Добавь примечание или <code>-</code> пропустить:", reply_markup=kb_back_admin())


@dp.message(AdminFlow.issue_note)
async def msg_admin_note(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    note = "" if raw == "-" else raw
    data = await state.get_data()
    await state.clear()
    telegram_id = data.get("telegram_id", 0)
    license_data = await db.create_license(
        plan=data["plan_id"],
        hwid=data.get("hwid", ""),
        telegram_id=telegram_id,
        note=note,
    )
    plan = PLANS.get(data["plan_id"], {})
    key = license_data.get("key", "")
    await message.answer(
        f"✅ <b>Ключ создан!</b>\n\n"
        f"📦 {plan.get('name', data['plan_id'])} | до {license_data['expires_at'][:10]}\n"
        f"💻 HWID: <code>{data.get('hwid') or 'не задан'}</code>\n"
        f"📝 {note or '—'}\n\n"
        f"🔑 <code>{key}</code>",
        reply_markup=kb_admin(),
    )
    if telegram_id:
        try:
            await bot.send_message(
                telegram_id,
                f"🎉 <b>Ваш лицензионный ключ FMail Sender</b>\n\n"
                f"📦 {plan.get('name', data['plan_id'])} | до {license_data['expires_at'][:10]}\n\n"
                f"🔑 <code>{key}</code>\n\nВведите в программе на экране активации."
            )
            await message.answer(f"✅ Ключ отправлен получателю (ID: <code>{telegram_id}</code>)")
        except Exception as e:
            await message.answer(f"⚠️ Не удалось отправить: {e}\nОтправьте вручную: <code>{key}</code>")


# ─── Admin Set Download URL ───────────────────────────────────────────────────

@dp.callback_query(F.data == "admin_set_download")
async def cb_admin_set_download(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        return
    try:
        current = await db.get_setting("download_url") or DOWNLOAD_URL
    except Exception:
        current = DOWNLOAD_URL
    await state.set_state(AdminFlow.set_download_url)
    await send_or_edit(
        query,
        f"🔗 <b>Ссылка скачивания</b>\n\nТекущая:\n<code>{current}</code>\n\nОтправь новую прямую ссылку:",
        reply_markup=kb_back_admin(),
    )


@dp.message(AdminFlow.set_download_url)
async def msg_admin_set_download_url(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    url = (message.text or "").strip()
    await state.clear()
    if not url.startswith("http"):
        await message.answer("❌ Некорректная ссылка. Должна начинаться с http(s)://", reply_markup=kb_admin())
        return
    await db.set_setting("download_url", url)
    await message.answer(f"✅ Ссылка скачивания обновлена:\n<code>{url}</code>", reply_markup=kb_admin())











































# ─── Admin Upload File ────────────────────────────────────────────────────────

@dp.callback_query(F.data == "admin_upload_file")
async def cb_admin_upload_file(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        return
    await state.set_state(AdminFlow.upload_file)
    await send_or_edit(
        query,
        "📤 <b>Загрузка .exe файла</b>\n\n"
        "Отправь файл <b>FMailSender.exe</b> прямо в этот чат.\n"
        "Файл сохранится на сервере и ссылка скачивания обновится автоматически.",
        reply_markup=kb_back_admin(),
    )


@dp.message(AdminFlow.upload_file)
async def msg_upload_file(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    doc = message.document
    if not doc:
        await message.answer("❌ Отправь файл документом (не фото/видео).", reply_markup=kb_back_admin())
        return

    fname = doc.file_name or "FMailSender.exe"
    fname = "".join(c for c in fname if c.isalnum() or c in "._-")
    if not fname:
        fname = "FMailSender.exe"
    if not fname.lower().endswith(".exe"):
          await message.answer("❌ Только .exe файлы разрешены.", reply_markup=kb_back_admin())
          await state.clear()
          return
  
    await message.answer(f"⏳ Загружаю <b>{fname}</b>… Подождите.")

    try:
        os.makedirs("downloads", exist_ok=True)
        save_path = os.path.join("downloads", fname)
        # BUG-FIX: используем bot.download() — токен не попадает в логи URL
        file_bytes = await bot.download(doc.file_id)
        with open(save_path, "wb") as f:
            f.write(file_bytes.read())

        server_host = os.environ.get("SERVER_HOST", "")
        if not server_host:
            server_host = f"{API_HOST}:{API_PORT}" if API_HOST != "0.0.0.0" else f"localhost:{API_PORT}"
        scheme = "https" if os.environ.get("SERVER_HTTPS") else "http"
        download_url = f"{scheme}://{server_host}/v1/download/{fname}"
        await db.set_setting("download_url", download_url)
        await state.clear()
        await message.answer(
            f"✅ <b>Файл загружен!</b>\n\n"
            f"📁 <code>{fname}</code>\n"
            f"🔗 <code>{download_url}</code>\n\nСсылка скачивания обновлена.",
            reply_markup=kb_admin(),
        )
        logger.info("Admin %d uploaded: %s → %s", message.from_user.id, fname, save_path)
    except Exception as e:
        logger.error("File upload error: %s", e)
        await state.clear()
        await message.answer(f"❌ Ошибка при загрузке: {e}", reply_markup=kb_admin())


# ─── Admin Clear Keys ─────────────────────────────────────────────────────────

@dp.callback_query(F.data == "admin_clear_keys")
async def cb_admin_clear_keys(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        return
    await state.set_state(AdminFlow.confirm_clear)
    await send_or_edit(
        query,
        "⚠️ <b>УДАЛЕНИЕ ВСЕХ КЛЮЧЕЙ</b>\n\n"
        "Это действие необратимо — все лицензии и платежи будут удалены.\n\n"
        "Напиши <b>ПОДТВЕРЖДАЮ</b> для подтверждения:",
        reply_markup=kb_back_admin(),
    )


@dp.message(AdminFlow.confirm_clear)
async def msg_admin_confirm_clear(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if (message.text or "").strip().upper() == "ПОДТВЕРЖДАЮ":
        count = await db.delete_all_licenses()
        await state.clear()
        await message.answer(f"🗑 <b>Готово.</b> Удалено {count} записей из базы данных.", reply_markup=kb_admin())
    else:
        await state.clear()
        await message.answer("❌ Операция отменена.", reply_markup=kb_admin())


# ─── Admin Revoke ─────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "admin_revoke")
async def cb_admin_revoke(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        return
    await state.set_state(AdminFlow.revoke_key)
    await send_or_edit(query, "🚫 <b>Отзыв ключа</b>\n\nОтправь лицензионный ключ для отзыва:", reply_markup=kb_back_admin())


@dp.message(AdminFlow.revoke_key)
async def msg_admin_revoke(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    key = (message.text or "").strip().upper()
    await state.clear()
    success = await db.revoke_license(key)
    text = f"✅ Ключ <code>{key}</code> отозван." if success else f"❌ Ключ не найден: <code>{key}</code>"
    await message.answer(text, reply_markup=kb_admin())


# ─── Admin Prices ─────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "admin_prices")
async def cb_admin_prices(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        return
    await state.set_state(AdminFlow.set_price_plan)
    lines = ["💲 <b>Текущие цены:</b>\n"]
    for plan_id, plan in PLANS.items():
        price = await db.get_plan_price(plan_id)
        lines.append(f"{plan['name']}: <b>${price:.2f} USDT</b>")
    lines.append("\nВыбери план для изменения:")
    await send_or_edit(query, "\n".join(lines), reply_markup=kb_admin_plans())


@dp.callback_query(F.data.startswith("admin_plan:"), AdminFlow.set_price_plan)
async def cb_admin_price_plan(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        return
    plan_id = query.data.split(":", 1)[1]
    current = await db.get_plan_price(plan_id)
    await state.update_data(price_plan_id=plan_id)
    await state.set_state(AdminFlow.set_price_value)
    await send_or_edit(
        query,
        f"💲 {PLANS[plan_id]['name']}: <b>${current:.2f}</b>\n\nОтправь новую цену в USDT:",
        reply_markup=kb_back_admin(),
    )


@dp.message(AdminFlow.set_price_value)
async def msg_admin_price_value(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        new_price = float((message.text or "").strip().replace(",", "."))
        if new_price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи корректную цену (например: 25.00)")
        return
    data = await state.get_data()
    plan_id = data["price_plan_id"]
    await db.set_setting(f"price_{plan_id}", str(new_price))
    await state.clear()
    await message.answer(
        f"✅ Цена <b>{PLANS.get(plan_id, {}).get('name', plan_id)}</b> → <b>${new_price:.2f} USDT</b>",
        reply_markup=kb_admin(),
    )


# ─── Admin Broadcast ──────────────────────────────────────────────────────────

@dp.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        return
    await state.set_state(AdminFlow.broadcast_text)
    await send_or_edit(
        query,
        "📢 <b>Рассылка</b>\n\nОтправь текст сообщения (HTML поддерживается):",
        reply_markup=kb_back_admin(),
    )


@dp.message(AdminFlow.broadcast_text)
async def msg_admin_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = message.text or ""
    await state.clear()
    user_ids = await db.get_distinct_user_ids()
    sent = 0
    failed = 0
    # FIX СРЕДН-2: рассылка в фоновом asyncio.Task — бот не блокируется во время отправки
    from aiogram.exceptions import TelegramRetryAfterError, TelegramForbiddenError
    admin_id = message.from_user.id
    await message.answer(
        f"📢 <b>Рассылка запущена в фоне</b>\n👥 Получателей: {len(user_ids)}\n\nПо завершении получишь отчёт.",
        reply_markup=kb_admin(),
    )
    asyncio.create_task(_broadcast_task(admin_id, user_ids, text))


async def _broadcast_task(admin_id: int, user_ids: list, text: str) -> None:
    """Фоновая рассылка — не блокирует event loop."""
    from aiogram.exceptions import TelegramRetryAfterError, TelegramForbiddenError
    sent = 0; failed = 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, text)
            sent += 1
            await asyncio.sleep(0.04)
        except TelegramRetryAfterError as e:
            logger.warning("Рассылка: rate limit %ds", e.retry_after)
            await asyncio.sleep(e.retry_after + 1)
            try:
                await bot.send_message(uid, text)
                sent += 1
            except Exception:
                failed += 1
        except TelegramForbiddenError:
            failed += 1
        except Exception:
            failed += 1
    try:
        await bot.send_message(admin_id,
            f"📢 <b>Рассылка завершена</b>\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}")
    except Exception as _e:
        logger.warning("broadcast_end_notify: не удалось отправить отчёт admin=%s: %s", admin_id, _e)


# ─── Admin Command ────────────────────────────────────────────────────────────

@dp.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    stats = await db.get_stats()
    text = (
        f"⚙️ <b>Панель администратора</b>\n\n"
        f"✅ Активных: <b>{stats.get('active', 0)}</b>\n"
        f"👥 Пользователей: <b>{stats.get('users', 0)}</b>"
    )
    await message.answer(text, reply_markup=kb_admin())


# ─── Moderator Panel ─────────────────────────────────────────────────────────

@dp.callback_query(F.data == "mod_panel")
async def cb_mod_panel(query: CallbackQuery, state: FSMContext):
    if not is_admin_or_mod(query.from_user.id):
        return
    await state.clear()
    stats = await db.get_stats()
    tickets_note = f"\n🎫 Открытых тикетов: <b>{stats.get('open_tickets', 0)}</b>" if stats.get("open_tickets") else ""
    text = (
        f"🛡 <b>Панель модератора</b>\n\n"
        f"✅ Активных лицензий: <b>{stats.get('active', 0)}</b>\n"
        f"👥 Пользователей: <b>{stats.get('users', 0)}</b>"
        f"{tickets_note}"
    )
    await send_or_edit(query, text, reply_markup=kb_moderator())


@dp.callback_query(F.data == "mod_stats")
async def cb_mod_stats(query: CallbackQuery):
    if not is_admin_or_mod(query.from_user.id):
        return
    stats = await db.get_stats()
    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"✅ Активных лицензий: <b>{stats.get('active', 0)}</b>\n"
        f"📦 Всего лицензий: <b>{stats.get('total', 0)}</b>\n"
        f"💳 Оплаченных заказов: <b>{stats.get('paid', 0)}</b>\n"
        f"👥 Пользователей: <b>{stats.get('users', 0)}</b>\n"
        f"🎫 Открытых тикетов: <b>{stats.get('open_tickets', 0)}</b>"
    )
    await send_or_edit(query, text, reply_markup=kb_back_mod())


@dp.callback_query(F.data == "mod_list")
async def cb_mod_list(query: CallbackQuery):
    if not is_admin_or_mod(query.from_user.id):
        return
    licenses = await db.get_all_licenses(limit=10)
    if not licenses:
        await send_or_edit(query, "📋 Лицензий пока нет.", reply_markup=kb_back_mod())
        return
    parts = [f"📋 <b>Последние {len(licenses)} лицензий:</b>\n"]
    for lic in licenses:
        plan_name = PLANS.get(lic.get("plan", ""), {}).get("name", lic.get("plan", "—"))
        exp = lic.get("expires_at", "")[:10]
        hwid = lic.get("hwid") or "—"
        status = "✅" if lic.get("is_active") else "❌"
        parts.append(f"{status} <code>{lic['key']}</code>\n   {plan_name} | до {exp} | HWID: {hwid}")
        parts.append("")
    await send_or_edit(query, "\n".join(parts), reply_markup=kb_back_mod())


# ─── Moderator Issue Flow ─────────────────────────────────────────────────────

@dp.callback_query(F.data == "mod_issue")
async def cb_mod_issue(query: CallbackQuery, state: FSMContext):
    if not is_admin_or_mod(query.from_user.id):
        return
    await state.set_state(ModeratorFlow.issue_plan)
    await send_or_edit(query, "🎟 <b>Выдача ключа</b>\n\nВыбери тарифный план:", reply_markup=kb_admin_plans())


@dp.callback_query(F.data.startswith("admin_plan:"), ModeratorFlow.issue_plan)
async def cb_mod_plan_selected(query: CallbackQuery, state: FSMContext):
    if not is_admin_or_mod(query.from_user.id):
        return
    plan_id = query.data.split(":", 1)[1]
    await state.update_data(plan_id=plan_id)
    await state.set_state(ModeratorFlow.issue_telegram_id)
    plan = PLANS.get(plan_id, {})
    await send_or_edit(
        query,
        f"🎟 Тариф: <b>{plan.get('name', plan_id)}</b>\n\n"
        f"Отправь Telegram ID получателя (числовой) или <code>-</code> пропустить:",
        reply_markup=kb_back_mod(),
    )


@dp.message(ModeratorFlow.issue_telegram_id)
async def msg_mod_telegram_id(message: Message, state: FSMContext):
    if not is_admin_or_mod(message.from_user.id):
        return
    raw = (message.text or "").strip()
    telegram_id = 0
    if raw != "-":
        try:
            telegram_id = int(raw)
        except ValueError:
            await message.answer("❌ Telegram ID должен быть числом или <code>-</code>")
            return
    await state.update_data(telegram_id=telegram_id)
    await state.set_state(ModeratorFlow.issue_hwid)
    await message.answer("💻 Отправь HWID получателя или <code>-</code> пропустить:", reply_markup=kb_back_mod())


@dp.message(ModeratorFlow.issue_hwid)
async def msg_mod_hwid(message: Message, state: FSMContext):
    if not is_admin_or_mod(message.from_user.id):
        return
    raw = (message.text or "").strip()
    hwid = "" if raw == "-" else raw.upper()
    await state.update_data(hwid=hwid)
    await state.set_state(ModeratorFlow.issue_note)
    await message.answer("📝 Добавь примечание или <code>-</code> пропустить:", reply_markup=kb_back_mod())


@dp.message(ModeratorFlow.issue_note)
async def msg_mod_note(message: Message, state: FSMContext):
    if not is_admin_or_mod(message.from_user.id):
        return
    raw = (message.text or "").strip()
    note = "" if raw == "-" else raw
    data = await state.get_data()
    await state.clear()
    telegram_id = data.get("telegram_id", 0)
    license_data = await db.create_license(
        plan=data["plan_id"],
        hwid=data.get("hwid", ""),
        telegram_id=telegram_id,
        note=note,
    )
    plan = PLANS.get(data["plan_id"], {})
    key = license_data.get("key", "")
    await message.answer(
        f"✅ <b>Ключ создан!</b>\n\n"
        f"📦 {plan.get('name', data['plan_id'])} | до {license_data['expires_at'][:10]}\n"
        f"💻 HWID: <code>{data.get('hwid') or 'не задан'}</code>\n"
        f"📝 {note or '—'}\n\n"
        f"🔑 <code>{key}</code>",
        reply_markup=kb_moderator(),
    )
    if telegram_id:
        try:
            await bot.send_message(
                telegram_id,
                f"🎉 <b>Ваш лицензионный ключ FMail Sender</b>\n\n"
                f"📦 {plan.get('name', data['plan_id'])} | до {license_data['expires_at'][:10]}\n\n"
                f"🔑 <code>{key}</code>\n\nВведите в программе на экране активации."
            )
        except Exception as _e:
            logger.warning("mod_issue: failed to notify user %d: %s", telegram_id, _e)


# ─── Moderator Revoke Flow ────────────────────────────────────────────────────

@dp.callback_query(F.data == "mod_revoke")
async def cb_mod_revoke(query: CallbackQuery, state: FSMContext):
    if not is_admin_or_mod(query.from_user.id):
        return
    await state.set_state(ModeratorFlow.revoke_key)
    await send_or_edit(query, "🚫 <b>Отзыв ключа</b>\n\nОтправь лицензионный ключ для отзыва:", reply_markup=kb_back_mod())


@dp.message(ModeratorFlow.revoke_key)
async def msg_mod_revoke(message: Message, state: FSMContext):
    if not is_admin_or_mod(message.from_user.id):
        return
    key = (message.text or "").strip().upper()
    await state.clear()
    success = await db.revoke_license(key)
    text = f"✅ Ключ <code>{key}</code> отозван." if success else f"❌ Ключ не найден: <code>{key}</code>"
    await message.answer(text, reply_markup=kb_moderator())


# ─── Moderator Tickets ────────────────────────────────────────────────────────

@dp.callback_query(F.data == "mod_tickets")
async def cb_mod_tickets(query: CallbackQuery):
    if not is_admin_or_mod(query.from_user.id):
        return
    tickets = await db.get_open_tickets()
    if not tickets:
        await send_or_edit(query, "🎫 Открытых тикетов нет.", reply_markup=kb_back_mod())
        return
    rows = []
    for t in tickets[:15]:
        label = f"#{t['id']} {t.get('first_name', '')} @{t.get('username', '')}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"mod_ticket_view:{t['id']}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="mod_panel")])
    await send_or_edit(query, f"🎫 <b>Открытые тикеты ({len(tickets)}):</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("mod_ticket_view:"))
async def cb_mod_ticket_view(query: CallbackQuery, state: FSMContext):
    if not is_admin_or_mod(query.from_user.id):
        return
    ticket_id = int(query.data.split(":", 1)[1])
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await query.answer("Тикет не найден.", show_alert=True)
        return
    msgs = await db.get_ticket_messages(ticket_id)
    lines = [f"🎫 <b>Тикет #{ticket_id}</b> · {ticket.get('first_name', '')} @{ticket.get('username', '')}"]
    lines.append(f"📅 {ticket['created_at'][:16].replace('T', ' ')}\n")
    for m in msgs[-10:]:
        who = "👤" if m["role"] == "user" else "🛡"  # FIX C-2
        lines.append(f"{who} {m['text']}")
    close_row = (
        [[InlineKeyboardButton(text="✅ Закрыть тикет", callback_data=f"ticket_close:{ticket_id}")]]
        if ticket.get("status") == "open"
        else []
    )
    rows = [
        [InlineKeyboardButton(text="✍️ Ответить", callback_data=f"mod_ticket_reply:{ticket_id}")],
        *close_row,
        [InlineKeyboardButton(text="◀️ Назад к тикетам", callback_data="mod_tickets")],
    ]
    await send_or_edit(query, "\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("mod_ticket_reply:"))
async def cb_mod_ticket_reply_start(query: CallbackQuery, state: FSMContext):
    if not is_admin_or_mod(query.from_user.id):
        return
    ticket_id = int(query.data.split(":", 1)[1])
    await state.update_data(reply_ticket_id=ticket_id)
    await state.set_state(ModeratorFlow.ticket_reply)
    await send_or_edit(
        query,
        f"✍️ Введи ответ на тикет #{ticket_id}:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"mod_ticket_view:{ticket_id}")]
        ]),
    )


@dp.message(ModeratorFlow.ticket_reply)
async def msg_mod_ticket_reply(message: Message, state: FSMContext):
    if not is_admin_or_mod(message.from_user.id):
        return
    data = await state.get_data()
    ticket_id = data.get("reply_ticket_id")
    await state.clear()
    if not ticket_id:
        await message.answer("❌ Ошибка: тикет не найден.", reply_markup=kb_moderator())
        return
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await message.answer("❌ Тикет не найден.", reply_markup=kb_moderator())
        return
    reply_text = message.text or message.caption or ""
    file_id = ""
    file_type = ""
    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"
    elif message.voice:
        file_id = message.voice.file_id
        file_type = "voice"
    elif message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.audio:
        file_id = message.audio.file_id
        file_type = "audio"
    await db.add_ticket_message(ticket_id, message.from_user.id, "staff", reply_text, file_id, file_type)
    try:
        mod_info = f"@{message.from_user.username}" if message.from_user.username else str(message.from_user.id)
        header = f"📩 <b>Ответ по тикету #{ticket_id}</b>\n\n<i>— Поддержка ({mod_info})</i>"
        if file_id and file_type == "photo":
            await bot.send_photo(ticket["user_id"], file_id, caption=(f"{reply_text}\n\n{header}" if reply_text else header))
        elif file_id and file_type == "document":
            await bot.send_document(ticket["user_id"], file_id, caption=(f"{reply_text}\n\n{header}" if reply_text else header))
        elif file_id and file_type == "voice":
            await bot.send_voice(ticket["user_id"], file_id, caption=header)
        elif file_id and file_type == "video":
            await bot.send_video(ticket["user_id"], file_id, caption=(f"{reply_text}\n\n{header}" if reply_text else header))
        elif file_id and file_type == "audio":
            await bot.send_audio(ticket["user_id"], file_id, caption=(f"{reply_text}\n\n{header}" if reply_text else header))
        else:
            await bot.send_message(
                ticket["user_id"],
                f"📩 <b>Ответ по тикету #{ticket_id}</b>\n\n{reply_text}\n\n{header}",
            )
    except Exception as _e:
        logger.warning("mod_ticket_reply: failed to notify user: %s", _e)
    await message.answer(f"✅ Ответ отправлен по тикету #{ticket_id}.", reply_markup=kb_moderator())


# ─── Admin Manage Moderators ──────────────────────────────────────────────────

@dp.callback_query(F.data == "manage_moderators")
async def cb_manage_moderators(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        return
    await state.clear()
    mods = await db.get_all_moderators()
    env_mods = [uid for uid in MODERATOR_IDS if uid not in ADMIN_IDS]
    lines = ["👮 <b>Модераторы</b>\n"]
    if env_mods:
        lines.append(f"📌 Из env (постоянные): {', '.join(f'<code>{m}</code>' for m in env_mods)}")
    if mods:
        lines.append(f"\n🗃 Из БД:")
        for m in mods:
            lines.append(f"  · <code>{m['telegram_id']}</code> — добавил: {m.get('added_by') or '—'}")
    else:
        lines.append("\n<i>Модераторов в БД нет.</i>")
    rows = [
        [InlineKeyboardButton(text="➕ Добавить модератора", callback_data="admin_add_mod")],
    ]
    if mods:
        rows.append([InlineKeyboardButton(text="➖ Удалить модератора", callback_data="admin_remove_mod")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")])
    await send_or_edit(query, "\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data == "admin_add_mod")
async def cb_admin_add_mod(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        return
    await state.set_state(AdminFlow.add_moderator_id)
    await send_or_edit(
        query,
        "➕ <b>Добавить модератора</b>\n\nОтправь Telegram ID нового модератора:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="manage_moderators")]
        ]),
    )


@dp.message(AdminFlow.add_moderator_id)
async def msg_admin_add_mod(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    try:
        mod_id = int(raw)
    except ValueError:
        await message.answer("❌ Telegram ID должен быть числом.")
        return
    await state.clear()
    await db.add_moderator(mod_id, added_by=message.from_user.id)
    _moderator_ids.add(mod_id)
    await message.answer(
        f"✅ Модератор <code>{mod_id}</code> добавлен.",
        reply_markup=kb_admin(),
    )


@dp.callback_query(F.data == "admin_remove_mod")
async def cb_admin_remove_mod(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        return
    mods = await db.get_all_moderators()
    if not mods:
        await query.answer("Модераторов в БД нет.", show_alert=True)
        return
    rows = []
    for m in mods:
        label = f"❌ {m['telegram_id']} — добавил: {m.get('added_by') or '—'}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"admin_del_mod:{m['telegram_id']}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="manage_moderators")])
    await send_or_edit(query, "➖ <b>Выбери модератора для удаления:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("admin_del_mod:"))
async def cb_admin_del_mod(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return
    mod_id = int(query.data.split(":", 1)[1])
    await db.remove_moderator(mod_id)
    _moderator_ids.discard(mod_id)
    await query.answer(f"Модератор {mod_id} удалён.", show_alert=True)
    mods = await db.get_all_moderators()
    if not mods:
        await send_or_edit(query, "👮 Модераторов в БД больше нет.", reply_markup=kb_admin())
        return
    rows = []
    for m in mods:
        label = f"❌ {m['telegram_id']} — добавил: {m.get('added_by') or '—'}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"admin_del_mod:{m['telegram_id']}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="manage_moderators")])
    await send_or_edit(query, "➖ <b>Выбери модератора для удаления:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


# ─── FastAPI License Validation ──────────────────────────────────────────────

api_app = FastAPI(title="FMail Sender License API", docs_url=None, redoc_url=None)


class ActivateRequest(BaseModel):
    key: str
    hwid: str
    version: str = ""


@api_app.post("/v1/activate")
async def activate(req: ActivateRequest):
    key = req.key.strip().upper()
    hwid = req.hwid.strip().upper()

    lic = await db.get_license(key)
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    if not lic.get("is_active"):
        raise HTTPException(status_code=403, detail="License revoked")

    expires_at_str = lic["expires_at"]
    try:
        expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
    except Exception:
        raise HTTPException(status_code=500, detail="Invalid expiry date in database")

    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=403, detail="License expired")

    existing_hwid = lic.get("hwid", "")
    if existing_hwid and existing_hwid.upper() != hwid.upper():
        raise HTTPException(status_code=403, detail="HWID mismatch — license bound to another device")

    if not existing_hwid:
        await db.bind_hwid_to_license(key, hwid)

    payload = {
        "plan": lic.get("plan", ""),
        "max_threads": lic["max_threads"],
        "max_recipients": lic["max_recipients"],
        "exp": int(expires_at.timestamp()),
        "email": lic.get("email", ""),
        "hwid": hwid,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return {"token": token}


class VerifyRequest(BaseModel):
    key: str
    hwid: str


@api_app.post("/v1/verify")
async def verify_license(req: VerifyRequest):
    key = req.key.strip().upper()
    hwid = req.hwid.strip().upper()

    lic = await db.get_license(key)
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    if not lic.get("is_active"):
        raise HTTPException(status_code=403, detail="License revoked")

    expires_at_str = lic.get("expires_at", "")
    try:
        expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
    except Exception:
        raise HTTPException(status_code=500, detail="Invalid expiry date")

    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=403, detail="License expired")

    existing_hwid = lic.get("hwid", "")
    if existing_hwid and existing_hwid.upper() != hwid.upper():
        raise HTTPException(status_code=403, detail="HWID mismatch")

    return {"valid": True, "plan": lic.get("plan"), "expires_at": expires_at_str}


class AdminRevokeRequest(BaseModel):
      admin_secret: str = ""
      api_key: str = ""
      key: str


@api_app.post("/v1/admin/revoke")
async def admin_revoke(req: AdminRevokeRequest):
    provided = req.api_key or req.admin_secret
    expected = ADMIN_API_KEY or os.environ.get("ADMIN_REVOKE_SECRET", "")
    # constant-time сравнение — защита от timing-атаки на админ-секрет
    if not expected or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")
    revoked = await db.revoke_license(req.key.strip().upper())
    if not revoked:
        raise HTTPException(status_code=404, detail="License not found")
    return {"revoked": True, "key": req.key.upper()}


from fastapi.responses import FileResponse, HTMLResponse


@api_app.get("/v1/download/{filename}")
async def download_file(filename: str, key: str = ""):
    if not key:
        raise HTTPException(status_code=401, detail="License key required: ?key=YOUR_KEY")
    lic = await db.get_license(key.strip().upper())
    if not lic or not lic.get("is_active"):
        raise HTTPException(status_code=403, detail="Invalid or revoked license key")
    try:
        exp = datetime.fromisoformat(lic["expires_at"].replace("Z", "+00:00"))
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > exp:
            raise HTTPException(status_code=403, detail="License expired")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Invalid expiry date")
    safe = "".join(c for c in filename if c.isalnum() or c in "._-")
    if not safe or ".." in safe:
        raise HTTPException(status_code=400, detail="Invalid filename")
    allowed = {".exe"}
    ext = os.path.splitext(safe)[1].lower()
    if ext not in allowed:
        raise HTTPException(status_code=403, detail="File type not allowed")
    # FIX КРИТ-3: path traversal — проверяем resolved path
    from pathlib import Path as _Path
    _dl_dir = _Path("downloads").resolve()
    _file_path = (_dl_dir / safe).resolve()
    if not str(_file_path).startswith(str(_dl_dir)):
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    if not _file_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден на сервере")
    return FileResponse(str(_file_path), filename=safe, media_type="application/octet-stream")


@api_app.get("/health")
async def health():
    stats = await db.get_stats()
    return {
        "status": "ok",
        "service": "FMail Sender License API",
        "version": APP_VERSION,
        "active_licenses": stats.get("active", 0),
        "open_tickets": stats.get("open_tickets", 0),
    }



# ─── Публичная статус-страница ───────────────────────────────────────────────

import time as _time
_SERVER_START = _time.time()


@api_app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_web_panel(
    api_key: str = "",
    secret: str = "",
    x_admin_api_key: str = Header(default="", alias="X-Admin-Api-Key"),
):
    """fmail.shop/admin — защищённая веб-панель управления."""
    provided_key = api_key or x_admin_api_key or secret
    if not _verify_admin_key(provided_key):
        return HTMLResponse(
            content=(
                "<!DOCTYPE html><html><body style='font-family:sans-serif;background:#0f0f1a;"
                "color:#e2e8f0;display:flex;align-items:center;justify-content:center;height:100vh;margin:0'>"
                "<div style='text-align:center'><h2 style='color:#fc8181'>403 — Доступ запрещён</h2>"
                "<p style='color:#718096;margin-top:8px'>Передайте API-ключ: "
                "<code>?api_key=YOUR_KEY</code></p></div></body></html>"
            ),
            status_code=403,
        )
    try:
        stats = await db.get_stats()
        licenses = await db.get_all_licenses(limit=200)
        mods = await db.get_all_moderators()
        tickets = await db.get_open_tickets()
        dl_url  = await db.get_setting("download_url") or DOWNLOAD_URL
        zip_url = await db.get_setting("zip_url") or ""
        vt_url  = await db.get_setting("vt_url") or ""
    except Exception:
        stats = {}; licenses = []; mods = []; tickets = []
        dl_url = zip_url = vt_url = ""
    AK = provided_key

    def _lic_rows() -> str:
        # FIX C-1: защищаем от 500 при неожиданных данных
        try:
         rows = []
         for lic in licenses:
            plan_name = PLANS.get(lic.get("plan", ""), {}).get("name", lic.get("plan", "—"))
            exp = lic.get("expires_at", "")[:10]
            sc = "ok" if lic.get("is_active") else "rev"
            st = "✅ Активна" if lic.get("is_active") else "❌ Отозвана"
            key = lic.get("key", "—")
            uid = lic.get("telegram_id") or "—"
            hwid_v = lic.get("hwid") or "—"
            note_v = html.escape(lic.get("note") or "")
            hwid_disp = hwid_v[:16] + ("…" if len(str(hwid_v)) > 16 else "")
            rows.append(
                f"<tr class='lr'>"
                f"<td><span class='b {sc}'>{st}</span></td>"
                f"<td><code onclick=\"navigator.clipboard.writeText('{key}')\" title='Скопировать'>{key}</code></td>"
                f"<td>{plan_name}</td><td>{exp}</td><td>{uid}</td>"
                f"<td title='{hwid_v}'>{hwid_disp}</td>"
                f"<td>{note_v[:25]}</td>"
                f"<td><button class='bd' onclick=\"rv('{key}',this)\">Отозвать</button></td></tr>"
            )
         return "".join(rows) or "<tr><td colspan='8' class='em'>Нет лицензий</td></tr>"
        except Exception as _e:
            logger.warning("_lic_rows error: %s", _e)
            return "<tr><td colspan='8' class='em'>⚠️ Ошибка загрузки</td></tr>"

    def _ticket_rows() -> str:
        # FIX C-1: защищаем от 500 при неожиданных данных
        try:
         rows = []
         for t in tickets:
            fn = html.escape(str(t.get("first_name", "")))
            un = html.escape(str(t.get("username", "")))
            rows.append(
                f"<tr><td>#{t.get('id')}</td><td>{fn}</td><td>@{un}</td>"
                f"<td>{str(t.get('created_at', ''))[:16].replace('T', ' ')}</td></tr>"
            )
         return "".join(rows) or "<tr><td colspan='4' class='em'>Нет тикетов</td></tr>"
        except Exception as _e:
            logger.warning("_ticket_rows error: %s", _e)
            return "<tr><td colspan='4' class='em'>⚠️ Ошибка загрузки</td></tr>"

    from datetime import datetime, timezone
    now_utc = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    plan_opts = "".join(
        f'<option value="{pid}">{p["name"]}</option>' for pid, p in PLANS.items()
    )
    n_lic = len(licenses)
    s_active = stats.get("active", 0)
    s_total  = stats.get("total", 0)
    s_users  = stats.get("users", 0)
    s_paid   = stats.get("paid", 0)
    s_rev    = stats.get("revenue_usdt", 0.0)
    s_tick   = stats.get("open_tickets", 0)
    dl_url_e = html.escape(dl_url)
    zip_url_e = html.escape(zip_url)
    vt_url_e  = html.escape(vt_url)

    admin_html = f"""<!DOCTYPE html>
<html lang="ru"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FMail Admin Panel</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f0f1a;color:#e2e8f0;padding:20px 14px}}
h1{{font-size:1.4rem;font-weight:700;background:linear-gradient(135deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:3px}}
.sub{{color:#718096;font-size:.8rem;margin-bottom:22px}}
.sub a{{color:#667eea;text-decoration:none}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:22px}}
.stat{{background:#1a1a2e;border:1px solid #2d2d44;border-radius:10px;padding:14px}}
.stat-n{{font-size:1.6rem;font-weight:700;color:#90cdf4}}
.stat-l{{font-size:.72rem;color:#718096;margin-top:2px}}
section{{background:#1a1a2e;border:1px solid #2d2d44;border-radius:10px;padding:16px;margin-bottom:14px}}
h2{{font-size:.88rem;font-weight:600;margin-bottom:12px;color:#a0aec0;text-transform:uppercase;letter-spacing:.04em}}
table{{width:100%;border-collapse:collapse;font-size:.78rem}}
th{{text-align:left;padding:6px 8px;border-bottom:2px solid #2d2d44;color:#718096;font-weight:500}}
td{{padding:5px 8px;border-bottom:1px solid #1e1e35;vertical-align:middle}}
.lr:hover td{{background:rgba(102,126,234,.04)}}
code{{background:#2d2d44;padding:2px 4px;border-radius:3px;font-size:.72rem;cursor:pointer;white-space:nowrap}}
code:hover{{background:#3d3d5c;color:#90cdf4}}
.b{{padding:2px 7px;border-radius:20px;font-size:.7rem;font-weight:600;white-space:nowrap}}
.b.ok{{background:rgba(72,187,120,.15);color:#68d391}}
.b.rev{{background:rgba(252,129,129,.15);color:#fc8181}}
.em{{text-align:center;color:#718096;padding:18px}}
.form-row{{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;margin-bottom:10px}}
.field{{display:flex;flex-direction:column;gap:4px;flex:1;min-width:130px}}
.field label{{font-size:.73rem;color:#718096}}
input,select{{background:#0f0f1a;border:1px solid #3d3d5c;border-radius:6px;color:#e2e8f0;padding:6px 9px;font-size:.82rem;width:100%;outline:none}}
input[type=file]{{border-style:dashed;padding:10px}}
input:focus,select:focus{{border-color:#667eea}}
.btn{{padding:7px 14px;border:none;border-radius:6px;font-size:.82rem;font-weight:600;cursor:pointer;transition:opacity .15s;white-space:nowrap}}
.btn:hover{{opacity:.85}}
.bp{{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff}}
.bd{{background:rgba(252,129,129,.15);color:#fc8181;border:1px solid rgba(252,129,129,.3);padding:3px 9px;border-radius:4px;font-size:.72rem;font-weight:500;cursor:pointer}}
.bd:hover{{background:rgba(252,129,129,.3)}}
.alert{{padding:9px 12px;border-radius:6px;font-size:.8rem;margin-top:8px;display:none}}
.alert.s{{background:rgba(72,187,120,.15);border:1px solid rgba(72,187,120,.3);color:#68d391}}
.alert.e{{background:rgba(252,129,129,.15);border:1px solid rgba(252,129,129,.3);color:#fc8181}}
.sb{{margin-bottom:10px;max-width:380px}}
.tabs{{display:flex;gap:5px;margin-bottom:14px;flex-wrap:wrap}}
.tab{{padding:5px 12px;border-radius:6px;font-size:.8rem;cursor:pointer;color:#718096;border:1px solid #2d2d44}}
.tab.on,.tab:hover{{background:#2d2d44;color:#e2e8f0}}
.tp{{display:none}}.tp.on{{display:block}}
footer{{margin-top:18px;color:#4a5568;font-size:.7rem;text-align:center}}
progress{{width:100%;height:5px;border-radius:3px;margin-top:5px;accent-color:#667eea}}
.result-box{{background:#0f0f1a;border:1px solid #2d2d44;border-radius:6px;padding:10px;font-size:.83rem;margin-top:10px;display:none}}
</style></head><body>
<h1>⚙️ FMail Admin Panel</h1>
<div class="sub">
  Обновлено: {now_utc} &nbsp;·&nbsp;
  <a href="?api_key={AK}">Обновить</a> &nbsp;·&nbsp;
  <a href="/">Статус</a>
</div>

<div class="grid">
  <div class="stat"><div class="stat-n">{s_active}</div><div class="stat-l">Активных лицензий</div></div>
  <div class="stat"><div class="stat-n">{s_total}</div><div class="stat-l">Всего лицензий</div></div>
  <div class="stat"><div class="stat-n">{s_users}</div><div class="stat-l">Пользователей</div></div>
  <div class="stat"><div class="stat-n">{s_paid}</div><div class="stat-l">Оплачено</div></div>
  <div class="stat"><div class="stat-n">${s_rev:.2f}</div><div class="stat-l">Выручка USDT</div></div>
  <div class="stat"><div class="stat-n">{s_tick}</div><div class="stat-l">Тикетов</div></div>
</div>

<div class="tabs">
  <div class="tab on" onclick="tab('licenses')">📋 Лицензии ({n_lic})</div>
  <div class="tab" onclick="tab('create')">➕ Создать ключ</div>
  <div class="tab" onclick="tab('settings')">🔗 Ссылки</div>
  <div class="tab" onclick="tab('upload')">📤 Загрузить файл</div>
  <div class="tab" onclick="tab('tickets')">🎫 Тикеты ({s_tick})</div>
</div>

<!-- Лицензии -->
<div class="tp on" id="tp-licenses">
<section>
  <h2>📋 Лицензии</h2>
  <div id="rv-alert" class="alert"></div>
  <input class="sb" id="srch" placeholder="🔍 Поиск по ключу, HWID, TG ID, примечанию…" oninput="flt(this.value)">
  <div style="overflow-x:auto">
  <table id="lt">
    <thead><tr><th>Статус</th><th>Ключ</th><th>Тариф</th><th>Истекает</th><th>TG ID</th><th>HWID</th><th>Примечание</th><th></th></tr></thead>
    <tbody id="lb">{_lic_rows()}</tbody>
  </table></div>
</section>
</div>

<!-- Создать ключ -->
<div class="tp" id="tp-create">
<section>
  <h2>➕ Создать лицензионный ключ</h2>
  <div class="form-row">
    <div class="field"><label>Тариф</label><select id="c-plan">{plan_opts}</select></div>
    <div class="field"><label>Telegram ID (опц.)</label><input id="c-tg" placeholder="123456789" type="number"></div>
    <div class="field"><label>HWID (опц.)</label><input id="c-hwid" placeholder="A1B2C3D4…" style="text-transform:uppercase"></div>
    <div class="field"><label>Примечание</label><input id="c-note" placeholder="Для кого…"></div>
    <button class="btn bp" onclick="crLic()">✅ Создать</button>
  </div>
  <div id="cr-alert" class="alert"></div>
  <div class="result-box" id="cr-res">
    <b>Создан ключ:</b><br>
    <code id="cr-key" style="font-size:1rem;display:block;margin:7px 0;letter-spacing:.05em"></code>
    <span id="cr-exp" style="color:#718096;font-size:.76rem"></span><br>
    <button class="btn bp" style="margin-top:7px;padding:5px 10px;font-size:.78rem"
      onclick="navigator.clipboard.writeText(document.getElementById('cr-key').innerText)">📋 Скопировать</button>
  </div>
</section>
</div>

<!-- Ссылки -->
<div class="tp" id="tp-settings">
<section>
  <h2>🔗 Управление ссылками</h2>
  <div class="form-row">
    <div class="field"><label>Ссылка скачивания .exe</label>
      <input id="s-dl" value="{dl_url_e}" placeholder="https://…"></div>
    <button class="btn bp" onclick="saveSetting('download_url','s-dl','dl-a')">Сохранить</button>
  </div>
  <div id="dl-a" class="alert"></div>












</section>
</div>

<!-- Загрузить файл -->
<div class="tp" id="tp-upload">
<section>
  <h2>📤 Загрузить .exe / .zip на сервер</h2>
  <p style="color:#718096;font-size:.8rem;margin-bottom:12px">
    Файл сохраняется в <code>downloads/</code> и доступен через
    <code>/v1/download/filename.exe?key=KEY</code>
  </p>
  <div class="form-row">
    <div class="field"><label>Файл (.exe)</label>
      <input id="ul-f" type="file" accept=".exe"></div>
    <button class="btn bp" onclick="ulFile()">📤 Загрузить</button>
  </div>
  <div id="ul-alert" class="alert"></div>
  <progress id="ul-prog" value="0" max="100" style="display:none"></progress>
</section>
</div>

<!-- Тикеты -->
<div class="tp" id="tp-tickets">
<section>
  <h2>🎫 Открытые тикеты</h2>
  <table>
    <thead><tr><th>#</th><th>Имя</th><th>Username</th><th>Дата</th></tr></thead>
    <tbody>{_ticket_rows()}</tbody>
  </table>
</section>
</div>

<footer>FMail Sender v{APP_VERSION} · powered by fmailsender.com</footer>

<script>
const AK="{AK}",BASE=window.location.origin;
function tab(n){{
  document.querySelectorAll('.tab,.tp').forEach(e=>e.classList.remove('on'));
  const t=[...document.querySelectorAll('.tab')].find(t=>t.getAttribute('onclick').includes(n));
  if(t)t.classList.add('on');
  const p=document.getElementById('tp-'+n);
  if(p)p.classList.add('on');
}}
function showAlert(id,msg,ok){{
  const el=document.getElementById(id);if(!el)return;
  el.className='alert '+(ok?'s':'e');el.textContent=msg;el.style.display='block';
  setTimeout(()=>el.style.display='none',5000);
}}
function flt(q){{
  const r=document.querySelectorAll('#lb .lr'),ql=q.toLowerCase();
  r.forEach(row=>row.style.display=(!ql||row.textContent.toLowerCase().includes(ql))?'':'none');
}}
async function rv(key,btn){{
  if(!confirm('Отозвать ключ '+key+'?'))return;
  btn.disabled=true;
  try{{
    const fd=new FormData();fd.append('api_key',AK);fd.append('key',key);
    const r=await fetch(BASE+'/v1/admin/web/revoke-license',{{method:'POST',body:fd}});
    const d=await r.json();
    if(d.ok){{
      const sp=btn.closest('tr').querySelector('.b');
      sp.className='b rev';sp.textContent='❌ Отозвана';btn.remove();
      showAlert('rv-alert','✅ Ключ '+key+' отозван',true);
    }}else showAlert('rv-alert','❌ Не найден: '+key,false);
  }}catch(e){{showAlert('rv-alert','❌ '+e,false);}}
  btn.disabled=false;
}}
async function crLic(){{
  const fd=new FormData();
  fd.append('api_key',AK);
  fd.append('plan',document.getElementById('c-plan').value);
  fd.append('telegram_id',document.getElementById('c-tg').value||'');
  fd.append('hwid',document.getElementById('c-hwid').value||'');
  fd.append('note',document.getElementById('c-note').value||'');
  try{{
    const r=await fetch(BASE+'/v1/admin/web/create-license',{{method:'POST',body:fd}});
    const d=await r.json();
    if(d.ok){{
      document.getElementById('cr-key').textContent=d.key;
      document.getElementById('cr-exp').textContent='Истекает: '+(d.expires_at||'').slice(0,10);
      document.getElementById('cr-res').style.display='block';
      showAlert('cr-alert','✅ Ключ создан!',true);
    }}else showAlert('cr-alert','❌ '+(d.detail||JSON.stringify(d)),false);
  }}catch(e){{showAlert('cr-alert','❌ '+e,false);}}
}}
async function saveSetting(key,inputId,alertId){{
  const val=document.getElementById(inputId).value;
  const fd=new FormData();
  fd.append('api_key',AK);fd.append('setting_key',key);fd.append('setting_value',val);
  try{{
    const r=await fetch(BASE+'/v1/admin/web/set-setting',{{method:'POST',body:fd}});
    const d=await r.json();showAlert(alertId,d.ok?'✅ Сохранено':'❌ Ошибка',d.ok);
  }}catch(e){{showAlert(alertId,'❌ '+e,false);}}
}}
async function ulFile(){{
  const file=document.getElementById('ul-f').files[0];
  if(!file){{showAlert('ul-alert','❌ Выберите файл',false);return;}}
  const fd=new FormData();fd.append('api_key',AK);fd.append('file',file);
  const prog=document.getElementById('ul-prog');prog.style.display='block';prog.value=25;
  try{{
    const r=await fetch(BASE+'/v1/admin/web/upload',{{method:'POST',body:fd}});
    prog.value=100;const d=await r.json();
    if(d.ok)showAlert('ul-alert','✅ Загружен: '+d.filename+' ('+Math.round(d.size/1024)+' KB)',true);
    else showAlert('ul-alert','❌ '+(d.detail||JSON.stringify(d)),false);
  }}catch(e){{showAlert('ul-alert','❌ '+e,false);}}
  setTimeout(()=>{{prog.style.display='none';prog.value=0;}},2000);
}}
</script>
</body></html>"""
    return HTMLResponse(content=admin_html)


@api_app.post("/v1/admin/web/create-license", include_in_schema=False)
async def web_create_license(
    api_key: str = Form(""),
    plan: str = Form(...),
    telegram_id: str = Form(""),
    hwid: str = Form(""),
    note: str = Form(""),
):
    if not _verify_admin_key(api_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        tg_id = int(telegram_id) if telegram_id.strip().isdigit() else 0
        lic = await db.create_license(plan=plan, hwid=hwid.strip().upper(), telegram_id=tg_id, note=note.strip())
        from fastapi.responses import JSONResponse
        return JSONResponse({"ok": True, "key": lic["key"], "expires_at": lic["expires_at"]})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@api_app.post("/v1/admin/web/revoke-license", include_in_schema=False)
async def web_revoke_license(api_key: str = Form(""), key: str = Form(...)):
    if not _verify_admin_key(api_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    revoked = await db.revoke_license(key.strip().upper())
    from fastapi.responses import JSONResponse
    return JSONResponse({"ok": revoked, "key": key.upper()})


@api_app.post("/v1/admin/web/set-setting", include_in_schema=False)
async def web_set_setting(
    api_key: str = Form(""),
    setting_key: str = Form(...),
    setting_value: str = Form(""),
):
    if not _verify_admin_key(api_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    allowed_settings = {"download_url", "zip_url", "vt_url"}
    if setting_key not in allowed_settings:
        raise HTTPException(status_code=400, detail=f"Unknown setting. Allowed: {allowed_settings}")
    await db.set_setting(setting_key, setting_value.strip())
    from fastapi.responses import JSONResponse
    return JSONResponse({"ok": True, "key": setting_key})


@api_app.post("/v1/admin/web/upload", include_in_schema=False)
async def web_upload_file(api_key: str = Form(""), file: UploadFile = FastAPIFile(...)):
    if not _verify_admin_key(api_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    import os as _os
    from pathlib import Path as _Path
    ext = _os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".exe"}:
        raise HTTPException(status_code=400, detail="Allowed type: .exe only")
    safe = "".join(c for c in (file.filename or "upload") if c.isalnum() or c in "._-")
    dl_dir = _Path("downloads"); dl_dir.mkdir(exist_ok=True)
    dest = dl_dir / safe
    import asyncio as _asyncio
    def _write_sync():
        with dest.open("wb") as fout:
            while True:
                chunk = file.file.read(1024 * 1024)  # 1MB чанки — быстрая запись
                if not chunk:
                    break
                fout.write(chunk)
    await _asyncio.to_thread(_write_sync)
    from fastapi.responses import JSONResponse
    # FIX: авто-обновляем download_url → fmail.shop после web-загрузки
    _auto_url = f"https://fmail.shop/v1/download/{safe}"
    try:
        await db.set_setting("download_url", _auto_url)
    except Exception as _ue:
        logger.warning("Не удалось сохранить download_url: %s", _ue)
    return JSONResponse({"ok": True, "filename": safe, "size": dest.stat().st_size})

@api_app.get("/v1/admin/web/licenses", include_in_schema=False)
async def web_get_licenses(api_key: str = "", limit: int = 200, search: str = ""):
    if not _verify_admin_key(api_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    from fastapi.responses import JSONResponse
    lics = await db.get_all_licenses(limit=limit)
    if search:
        sl = search.lower()
        lics = [l for l in lics if sl in (str(l.get("key","")) + str(l.get("hwid",""))
                + str(l.get("telegram_id","")) + str(l.get("note",""))).lower()]
    return JSONResponse({"licenses": [dict(l) for l in lics], "total": len(lics)})


@api_app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def status_page():
    """fmail.shop — статус сервисов FMail Sender."""
    try:
        stats = await db.get_stats()
        active_count = stats.get("active", 0)
        total_count  = stats.get("total", 0)
        db_ok = True
    except Exception:
        active_count = total_count = 0
        db_ok = False
    try:
        _me = await bot.get_me()
        bot_username = _me.username
        bot_ok = True
    except Exception:
        bot_username = "FMaill_bot"
        bot_ok = False
    uptime_s = int(_time.time() - _SERVER_START)
    h, r = divmod(uptime_s, 3600)
    uptime_str = f"{h}ч {r // 60}м"
    api_badge  = '<span class="badge g"><span class="dot dg"></span>Работает</span>'
    bot_badge  = f'<span class="badge {"g" if bot_ok else "r"}"><span class="dot {"dg" if bot_ok else "dr"}"></span>{"Online" if bot_ok else "Offline"}</span>'
    db_badge   = f'<span class="badge {"g" if db_ok else "r"}"><span class="dot {"dg" if db_ok else "dr"}"></span>{"Online" if db_ok else "Error"}</span>'
    from datetime import datetime, timezone
    now_utc = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M")
    html = f"""<!DOCTYPE html>
<html lang="ru"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FMail Sender — Status</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f0f1a;color:#e2e8f0;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:40px 16px}}
.logo{{font-size:2rem;font-weight:700;background:linear-gradient(135deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:4px}}
.sub{{color:#718096;font-size:.9rem;margin-bottom:40px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;width:100%;max-width:860px}}
.card{{background:#1a1a2e;border:1px solid #2d2d44;border-radius:16px;padding:24px}}
.ct{{font-size:.72rem;text-transform:uppercase;letter-spacing:.1em;color:#718096;margin-bottom:14px}}
.row{{display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-bottom:1px solid #2d2d44}}
.row:last-child{{border-bottom:none}}
.val{{color:#90cdf4}}.ok{{color:#48bb78}}.err{{color:#fc8181}}
.badge{{display:inline-flex;align-items:center;padding:3px 10px;border-radius:99px;font-size:.75rem;font-weight:600}}
.g{{background:#1c4532;color:#48bb78}}.r{{background:#4a1942;color:#fc8181}}
.dot{{width:8px;height:8px;border-radius:50%;margin-right:5px}}
.dg{{background:#48bb78;box-shadow:0 0 6px #48bb78aa}}.dr{{background:#fc8181}}
.footer{{margin-top:36px;color:#4a5568;font-size:.78rem;text-align:center}}
</style></head><body>
<div class="logo">✉ FMail Sender</div>
<div class="sub">Мониторинг сервисов · fmail.shop</div>
<div class="grid">
  <div class="card">
    <div class="ct">Статус сервисов</div>
    <div class="row"><span>Лицензионный API</span>{api_badge}</div>
    <div class="row"><span>Telegram Bot</span>{bot_badge}</div>
    <div class="row"><span>База данных</span>{db_badge}</div>
  </div>
  <div class="card">
    <div class="ct">Статистика</div>
    <div class="row"><span>Всего лицензий</span><span class="val">{total_count}</span></div>
    <div class="row"><span>Активных лицензий</span><span class="ok">{active_count}</span></div>
    <div class="row"><span>Uptime</span><span class="val">{uptime_str}</span></div>
    <div class="row"><span>Версия</span><span class="val">v{APP_VERSION}</span></div>
  </div>
  <div class="card">
    <div class="ct">Подключение</div>
    <div class="row"><span>Bot</span><span class="val">@{bot_username}</span></div>
    <div class="row"><span>API</span><span class="val">fmail.shop/v1/</span></div>
    <div class="row"><span>Протокол</span><span class="badge g">HTTPS</span></div>
  </div>
</div>
<div class="footer">Обновлено: {now_utc} UTC &nbsp;·&nbsp; <a href="/health" style="color:#667eea">JSON API</a></div>
</body></html>"""
    return HTMLResponse(content=html)


# ─── Entry Point ─────────────────────────────────────────────────────────────

async def _poll_pending_payments():
    """FIX ERR-2: Background task — auto-confirms payments without user pressing 'Check'.
    Polls CryptoPay every 60s for all pending invoices. Idempotent — safe to run always.
    """
    await asyncio.sleep(15)  # initial delay to let DB init complete
    while True:
        try:
            pending = await db.get_pending_payments()
            for payment in pending:
                invoice_id = payment.get("invoice_id", "")
                if not invoice_id:
                    continue
                try:
                    paid = await crypto_client.check_invoice(
                        invoice_id,
                        expected_amount=payment.get("amount"),
                        expected_asset="USDT",
                    )
                    if paid:
                        license_data = await db.create_license_for_payment(
                            invoice_id=invoice_id,
                            plan=payment["plan"],
                            hwid=payment.get("hwid", ""),
                            telegram_id=payment.get("telegram_id", 0),
                        )
                        user_id = payment.get("telegram_id", 0)
                        plan_name = PLANS.get(payment.get("plan", ""), {}).get("name", payment.get("plan", ""))
                        try:
                            await bot.send_message(
                                user_id,
                                f"✅ <b>Оплата подтверждена автоматически!</b>\n\n"
                                f"📦 Тариф: <b>{plan_name}</b>\n\n"
                                f"🔑 <b>Ваш лицензионный ключ:</b>\n<code>{license_data['key']}</code>\n\n"
                                f"Введите его на экране активации программы.\n"
                                f"💻 HWID: <code>{payment.get('hwid') or 'привязывается при первой активации'}</code>",
                                reply_markup=kb_main(is_admin(user_id), is_mod_user=is_moderator(user_id)),
                                parse_mode="HTML",
                            )
                        except Exception as notify_err:
                            logger.warning("Failed to notify user %d about auto payment: %s", user_id, notify_err)
                        logger.info("Auto-confirmed payment invoice_id=%s for user=%d", invoice_id, user_id)
                except Exception as e:
                    logger.warning("poll_payment error for invoice %s: %s", invoice_id, e)
        except Exception as e:
            logger.error("Payment poller error: %s", e)
        await asyncio.sleep(60)  # poll every 60 seconds


async def main():
    global _release_cache_lock
    _release_cache_lock = asyncio.Lock()  # BUG-FIX: инициализируем Lock внутри event loop
    await db.init_db()
    # Загружаем модераторов из БД в in-memory set
    _db_mods = await db.get_all_moderators()
    for _m in _db_mods:
        if _m.get("telegram_id"):
            _moderator_ids.add(_m["telegram_id"])
    logger.info("Loaded moderators from DB: %d (env: %d)", len(_db_mods), len(MODERATOR_IDS))
    # FIX: загружаем капчу и условия из БД — in-memory кэш переживёт перезапуск
    _cap, _terms = await get_all_passed_users()
    _captcha_passed.update(_cap)
    _terms_accepted.update(_terms)
    logger.info("Loaded from DB: captcha_passed=%d, terms_accepted=%d", len(_cap), len(_terms))
    logger.info("Starting FMail Sender Bot + API v%s...", APP_VERSION)

    # NO_SSL=1 → nginx/Cloudflare обрабатывает TLS (рекомендуется в production)
    # NO_SSL не задан → uvicorn использует self-signed сертификат из ssl/
    _use_ssl = not os.environ.get("NO_SSL")
    _ssl_kwargs: dict = {}
    if _use_ssl:
        _ssl_kwargs = {
            "ssl_certfile": os.path.join(os.path.dirname(__file__), "ssl", "cert.pem"),
            "ssl_keyfile": os.path.join(os.path.dirname(__file__), "ssl", "key.pem"),
        }
    config = uvicorn.Config(
        api_app, host=API_HOST, port=API_PORT,
        log_level="warning", loop="none",
        **_ssl_kwargs,
    )
    server = uvicorn.Server(config)

    try:
        await asyncio.gather(
            dp.start_polling(bot, skip_updates=True),
            server.serve(),
            _poll_pending_payments(),
        )
    finally:
        await crypto_client.close()


if __name__ == "__main__":
    asyncio.run(main())
