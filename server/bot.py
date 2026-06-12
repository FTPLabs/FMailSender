"""
FMail Sender — Telegram Bot + FastAPI License Server v2.5.0
Минималистичный интерфейс: Личный кабинет, Купить, Скачать, Поддержка.
"""
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional

import jwt
import uvicorn
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import database as db
from config import ADMIN_IDS, BOT_TOKEN, JWT_SECRET, KEY_PREFIX, PLANS, DOWNLOAD_URL
from crypto_pay import crypto_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("bot")

from aiogram.client.default import DefaultBotProperties
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


# ─── FSM States ────────────────────────────────────────────────────────────

class BuyFlow(StatesGroup):
    waiting_hwid = State()
    waiting_payment = State()


class SupportFlow(StatesGroup):
    waiting_message = State()


class AdminFlow(StatesGroup):
    issue_plan = State()
    issue_telegram_id = State()
    issue_hwid = State()
    issue_note = State()
    set_price_plan = State()
    set_price_value = State()
    revoke_key = State()
    broadcast_text = State()
    confirm_clear = State()
    set_download_url = State()


# ─── Keyboards ──────────────────────────────────────────────────────────────

def kb_main(is_admin_user: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="👤 Личный кабинет", callback_data="menu_cabinet")],
        [
            InlineKeyboardButton(text="💳 Купить лицензию", callback_data="menu_buy"),
            InlineKeyboardButton(text="📥 Скачать", callback_data="menu_download"),
        ],
        [InlineKeyboardButton(text="🎫 Поддержка", callback_data="menu_support")],
    ]
    if is_admin_user:
        rows.append([InlineKeyboardButton(text="⚙️ Панель администратора", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_plans() -> InlineKeyboardMarkup:
    rows = []
    for plan_id, plan in PLANS.items():
        if plan.get("admin_only"):
            continue
        rows.append([InlineKeyboardButton(
            text=f"{plan['name']} — ${plan['price_usdt']:.2f} USDT",
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


def kb_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟 Выдать ключ", callback_data="admin_issue")],
        [InlineKeyboardButton(text="📋 Все лицензии", callback_data="admin_list")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="💲 Изменить цены", callback_data="admin_prices")],
        [InlineKeyboardButton(text="🚫 Отозвать ключ", callback_data="admin_revoke")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔗 Ссылка скачивания", callback_data="admin_set_download")],
        [InlineKeyboardButton(text="🗑 Удалить все ключи", callback_data="admin_clear_keys")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu_main")],
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


# ─── Helpers ────────────────────────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _get_active_license(licenses: list) -> Optional[dict]:
    """Возвращает первую активную не истёкшую лицензию."""
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
        except Exception:
            pass
    return None


async def send_or_edit(message_or_query, text: str, reply_markup=None, **kwargs):
    if isinstance(message_or_query, CallbackQuery):
        try:
            await message_or_query.message.edit_text(text, reply_markup=reply_markup, **kwargs)
        except Exception:
            await message_or_query.message.answer(text, reply_markup=reply_markup, **kwargs)
        await message_or_query.answer()
    else:
        await message_or_query.answer(text, reply_markup=reply_markup, **kwargs)


# ─── /start ─────────────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    await db.upsert_user(user.id, user.username or "", user.first_name or "")
    text = (
        f"👋 Привет, <b>{user.first_name}</b>!\n\n"
        f"<b>FMail Sender</b> — профессиональный инструмент для email-рассылок.\n\n"
        f"Выбери действие:"
    )
    await message.answer(text, reply_markup=kb_main(is_admin(user.id)))


@dp.callback_query(F.data == "menu_main")
async def cb_menu_main(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await send_or_edit(query, "🏠 <b>Главное меню</b>", reply_markup=kb_main(is_admin(query.from_user.id)))


# ─── Личный кабинет ─────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_cabinet")
async def cb_cabinet(query: CallbackQuery):
    user = query.from_user
    licenses = await db.get_license_by_telegram(user.id)
    hwid = await db.get_user_hwid(user.id)
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

    await send_or_edit(query, "\n".join(lines), reply_markup=kb_back_main())


# ─── Скачать приложение ──────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_download")
async def cb_menu_download(query: CallbackQuery):
    user_id = query.from_user.id
    licenses = await db.get_license_by_telegram(user_id)
    active_lic = _get_active_license(licenses)

    try:
        dl_url = await db.get_setting("download_url") or DOWNLOAD_URL
    except Exception:
        dl_url = DOWNLOAD_URL

    if not active_lic:
        await send_or_edit(
            query,
            "❌ <b>Скачивание недоступно</b>\n\n"
            "У тебя нет активной подписки.\n"
            "Нажми «Купить лицензию» чтобы получить доступ.",
            reply_markup=kb_main(is_admin(user_id)),
        )
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬇️ Скачать FMailSender.exe", url=dl_url)],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu_main")],
    ])
    await send_or_edit(
        query,
        "📥 <b>Скачать FMail Sender</b>\n\n✅ Подписка активна. Нажми кнопку ниже:",
        reply_markup=kb,
    )


# ─── Поддержка (тикет) ───────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_support")
async def cb_support(query: CallbackQuery, state: FSMContext):
    await state.set_state(SupportFlow.waiting_message)
    text = (
        "🎫 <b>Поддержка</b>\n\n"
        "Опиши свою проблему подробно. Мы ответим в личные сообщения.\n\n"
        "📝 Напиши сообщение:"
    )
    await send_or_edit(query, text, reply_markup=kb_back_main())


@dp.message(SupportFlow.waiting_message)
async def msg_support(message: Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    hwid = await db.get_user_hwid(user.id)
    licenses = await db.get_license_by_telegram(user.id)
    active_lic = _get_active_license(licenses)
    plan_info = ""
    if active_lic:
        plan_name = PLANS.get(active_lic.get("plan", ""), {}).get("name", "—")
        plan_info = f"\n📦 Подписка: {plan_name}"

    ticket_text = (
        f"🎫 <b>Новый тикет поддержки</b>\n\n"
        f"👤 {user.first_name}"
        f"{(' (@' + user.username + ')') if user.username else ''}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"💻 HWID: <code>{hwid or 'не привязан'}</code>"
        f"{plan_info}\n\n"
        f"📝 <b>Сообщение:</b>\n{message.text or '(медиа-файл)'}"
    )

    sent = False
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, ticket_text)
            sent = True
        except Exception as e:
            logger.warning("Cannot send ticket to admin %d: %s", admin_id, e)

    if sent:
        await message.answer(
            "✅ <b>Тикет отправлен!</b>\n\nОтветим в личные сообщения. Обычно в течение 24 часов.",
            reply_markup=kb_main(is_admin(user.id)),
        )
    else:
        await message.answer(
            "⚠️ Не удалось отправить тикет. Попробуй позже.",
            reply_markup=kb_main(is_admin(user.id)),
        )


# ─── Buy Flow ───────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_buy")
async def cb_menu_buy(query: CallbackQuery):
    lines = ["💳 <b>Выбери тарифный план:</b>\n"]
    for plan_id, plan in PLANS.items():
        if plan.get("admin_only"):
            continue
        price = await db.get_plan_price(plan_id)
        lines.append(f"<b>{plan['name']}</b> — <b>${price:.2f} USDT</b>\n   {plan['description']}\n")
    await send_or_edit(query, "\n".join(lines), reply_markup=kb_plans())


@dp.callback_query(F.data.startswith("buy_plan:"))
async def cb_buy_plan(query: CallbackQuery, state: FSMContext):
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
        await send_or_edit(
            query,
            f"📦 <b>{PLANS[plan_id]['name']}</b>\n\n"
            "💻 Отправь свой <b>HWID</b> компьютера.\n"
            "Его можно скопировать на экране активации программы.",
            reply_markup=kb_back_main(),
        )


@dp.callback_query(F.data.startswith("use_hwid:"))
async def cb_use_hwid(query: CallbackQuery, state: FSMContext):
    hwid = query.data.split(":", 1)[1]
    data = await state.get_data()
    await _proceed_to_payment(query, state, hwid, data.get("plan_id", "week"))


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
            reply_markup=kb_main(is_admin(message.from_user.id)),
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
    try:
        paid = await crypto_client.check_invoice(invoice_id)
    except Exception as e:
        await query.answer(f"Ошибка проверки: {e}", show_alert=True)
        return
    if not paid:
        await query.answer("⏳ Оплата ещё не поступила. Попробуй через минуту.", show_alert=True)
        return
    payment = await db.get_payment(invoice_id)
    if not payment:
        await query.answer("❌ Платёж не найден.", show_alert=True)
        return
    existing_license = await db.get_payment_license(invoice_id)
    if existing_license:
        await send_or_edit(
            query,
            f"✅ Оплата подтверждена!\n\n🔑 <b>Ваш ключ:</b>\n<code>{existing_license}</code>\n\n"
            f"Введите его в программе на экране активации.",
            reply_markup=kb_main(is_admin(query.from_user.id)),
        )
        await state.clear()
        return
    license_data = await db.create_license(
        plan=payment["plan"],
        hwid=payment.get("hwid", ""),
        telegram_id=payment["telegram_id"],
    )
    await db.mark_payment_paid(invoice_id, license_data["key"])
    await state.clear()
    text = (
        f"✅ <b>Оплата подтверждена!</b>\n\n"
        f"📦 Тариф: <b>{PLANS.get(payment['plan'], {}).get('name', payment['plan'])}</b>\n\n"
        f"🔑 <b>Ваш лицензионный ключ:</b>\n<code>{license_data['key']}</code>\n\n"
        f"Введите его в программе на экране активации.\n"
        f"💻 HWID: <code>{payment.get('hwid') or 'привязывается при первой активации'}</code>"
    )
    await send_or_edit(query, text, reply_markup=kb_main(is_admin(query.from_user.id)))


# ─── Admin Panel ─────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "admin_panel")
async def cb_admin_panel(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        return
    await state.clear()
    stats = await db.get_stats()
    text = (
        f"⚙️ <b>Панель администратора</b>\n\n"
        f"✅ Активных лицензий: <b>{stats['active_licenses']}</b>\n"
        f"📦 Всего лицензий: <b>{stats['total_licenses']}</b>\n"
        f"💰 Выручка: <b>${stats['total_revenue_usdt']:.2f} USDT</b>\n"
        f"👥 Пользователей: <b>{stats['total_users']}</b>"
    )
    await send_or_edit(query, text, reply_markup=kb_admin())


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
        f"✅ Активных лицензий: <b>{stats['active_licenses']}</b>\n"
        f"📦 Всего лицензий: <b>{stats['total_licenses']}</b>\n"
        f"💳 Оплаченных заказов: <b>{stats['paid_orders']}</b>\n"
        f"👥 Пользователей: <b>{stats['total_users']}</b>\n"
        f"💰 Выручка: <b>${stats['total_revenue_usdt']:.2f} USDT</b>"
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
    await message.answer("💻 Отправь HWID получателя или <code>-</code> пропустить:")


@dp.message(AdminFlow.issue_hwid)
async def msg_admin_hwid(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    hwid = "" if raw == "-" else raw.upper()
    await state.update_data(hwid=hwid)
    await state.set_state(AdminFlow.issue_note)
    await message.answer("📝 Добавь примечание или <code>-</code> пропустить:")


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
    key = license_data["key"]
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


# ─── Admin Revoke ────────────────────────────────────────────────────────────

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


# ─── Admin Prices ────────────────────────────────────────────────────────────

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


# ─── Admin Broadcast ─────────────────────────────────────────────────────────

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
    # Собираем уникальные ID из всех пользователей с лицензиями
    licenses = await db.get_all_licenses(limit=5000)
    user_ids = list({lic["telegram_id"] for lic in licenses if lic.get("telegram_id")})
    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, text)
            sent += 1
            await asyncio.sleep(0.05)  # Telegram rate limit
        except Exception:
            failed += 1
    await message.answer(
        f"📢 Рассылка завершена\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}",
        reply_markup=kb_admin(),
    )


# ─── Admin Download URL ───────────────────────────────────────────────────────

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
async def msg_admin_set_download(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    url = (message.text or "").strip()
    if not url.startswith("http"):
        await message.answer("❌ Ссылка должна начинаться с http")
        return
    await db.set_setting("download_url", url)
    await state.clear()
    await message.answer(f"✅ Ссылка обновлена:\n<code>{url}</code>", reply_markup=kb_admin())


# ─── Admin Clear Keys ────────────────────────────────────────────────────────

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


# ─── Admin Command ────────────────────────────────────────────────────────────

@dp.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    stats = await db.get_stats()
    text = (
        f"⚙️ <b>Панель администратора</b>\n\n"
        f"✅ Активных: <b>{stats['active_licenses']}</b>\n"
        f"💰 Выручка: <b>${stats['total_revenue_usdt']:.2f} USDT</b>\n"
        f"👥 Пользователей: <b>{stats['total_users']}</b>"
    )
    await message.answer(text, reply_markup=kb_admin())


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

    # ИСПРАВЛЕНИЕ: единая timezone-aware проверка срока
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
        "plan": lic["plan"],
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
    """
    Проверка актуального статуса лицензии (для фоновой проверки клиентом).
    Возвращает 200 если ключ активен, 403 если отозван/истёк, 404 если не найден.
    """
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

    return {
        "valid": True,
        "plan": lic.get("plan"),
        "expires_at": expires_at_str,
    }


class AdminRevokeRequest(BaseModel):
    admin_secret: str
    key: str


@api_app.post("/v1/admin/revoke")
async def admin_revoke(req: AdminRevokeRequest):
    """
    HTTP-эндпоинт отзыва лицензии (только с секретным ключом администратора).
    """
    import os
    expected = os.environ.get("ADMIN_REVOKE_SECRET", "")
    if not expected or req.admin_secret != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
    revoked = await db.revoke_license(req.key.strip().upper())
    if not revoked:
        raise HTTPException(status_code=404, detail="License not found")
    return {"revoked": True, "key": req.key.upper()}


@api_app.get("/health")
async def health():
    stats = await db.get_stats()
    return {
        "status": "ok",
        "service": "FMail Sender License API",
        "version": "2.7.0",
        "active_licenses": stats.get("active_licenses", 0),
    }


# ─── Entry Point ─────────────────────────────────────────────────────────────

async def main():
    await db.init_db()
    logger.info("Starting FMail Sender Bot + API v2.7.0...")

    config = uvicorn.Config(
        api_app, host="0.0.0.0", port=8000,
        log_level="warning", loop="none",
    )
    server = uvicorn.Server(config)

    await asyncio.gather(
        dp.start_polling(bot, skip_updates=True),
        server.serve(),
    )


if __name__ == "__main__":
    asyncio.run(main())
