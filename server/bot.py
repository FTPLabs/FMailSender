"""
FMail Sender — Telegram Bot + FastAPI License Server
Запуск: python bot.py
"""
import asyncio
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
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
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import database as db
from config import ADMIN_IDS, BOT_TOKEN, JWT_SECRET, KEY_PREFIX, PLANS
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


class AdminFlow(StatesGroup):
    issue_plan = State()
    issue_telegram_id = State()   # FIX: новый шаг — Telegram ID получателя
    issue_hwid = State()
    issue_note = State()
    set_price_plan = State()
    set_price_value = State()
    revoke_key = State()
    broadcast_text = State()


# ─── Keyboards ──────────────────────────────────────────────────────────────

def kb_main(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="💳 Купить лицензию", callback_data="menu_buy")],
        [InlineKeyboardButton(text="🔑 Мои лицензии", callback_data="menu_my_licenses")],
        [InlineKeyboardButton(text="📋 Привязать HWID", callback_data="menu_set_hwid")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="menu_help")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel")])
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


def kb_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟 Выдать ключ", callback_data="admin_issue")],
        [InlineKeyboardButton(text="📋 Все лицензии", callback_data="admin_list")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="💲 Изменить цены", callback_data="admin_prices")],
        [InlineKeyboardButton(text="🚫 Отозвать ключ", callback_data="admin_revoke")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu_main")],
    ])


def kb_admin_plans() -> InlineKeyboardMarkup:
    rows = []
    for plan_id, plan in PLANS.items():
        label = plan["name"]
        if plan.get("admin_only"):
            label = f"[ПРОБНЫЙ] {label}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"admin_plan:{plan_id}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_back_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin_panel")]
    ])


def kb_back_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu_main")]
    ])


# ─── Helpers ────────────────────────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def fmt_license(lic: dict) -> str:
    exp = lic.get("expires_at", "")[:10]
    active = "✅ Активна" if lic.get("is_active") else "❌ Отозвана"
    hwid = lic.get("hwid") or "не привязан"
    plan_name = PLANS.get(lic.get("plan", ""), {}).get("name", lic.get("plan", ""))
    return (
        f"🔑 <code>{lic['key']}</code>\n"
        f"📦 План: <b>{plan_name}</b>\n"
        f"📅 Истекает: <b>{exp}</b>\n"
        f"💻 HWID: <code>{hwid}</code>\n"
        f"🔒 Статус: {active}"
    )


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
    admin = is_admin(user.id)
    text = (
        f"👋 Привет, <b>{user.first_name}</b>!\n\n"
        f"🚀 <b>FMail Sender Pro</b> — профессиональный инструмент для email-рассылок.\n\n"
        f"Выбери действие:"
    )
    await message.answer(text, reply_markup=kb_main(admin))


@dp.callback_query(F.data == "menu_main")
async def cb_menu_main(query: CallbackQuery, state: FSMContext):
    await state.clear()
    user = query.from_user
    admin = is_admin(user.id)
    text = (
        f"🏠 <b>Главное меню</b>\n\n"
        f"👤 {user.first_name} | ID: <code>{user.id}</code>"
    )
    await send_or_edit(query, text, reply_markup=kb_main(admin))


# ─── Help ───────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_help")
async def cb_help(query: CallbackQuery):
    text = (
        "📖 <b>Как начать работу:</b>\n\n"
        "1️⃣ Нажми <b>«Купить лицензию»</b> и выбери тарифный план\n"
        "2️⃣ Укажи свой <b>HWID</b> (отображается при открытии программы)\n"
        "3️⃣ Оплати через <b>CryptoBot</b> в USDT\n"
        "4️⃣ Получи лицензионный ключ и введи его в программе\n\n"
        "⚠️ <b>Важно:</b> Лицензия привязывается к HWID твоего компьютера.\n\n"
        "❓ Вопросы? Пиши в поддержку."
    )
    await send_or_edit(query, text, reply_markup=kb_back_main())


# ─── Set HWID ───────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_set_hwid")
async def cb_set_hwid(query: CallbackQuery, state: FSMContext):
    await state.set_state(BuyFlow.waiting_hwid)
    await state.update_data(hwid_only=True)
    text = (
        "💻 <b>Привязать HWID</b>\n\n"
        "Отправь свой HWID компьютера.\n"
        "Его можно скопировать прямо из программы на экране активации."
    )
    await send_or_edit(query, text, reply_markup=kb_back_main())


# ─── My Licenses ────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_my_licenses")
async def cb_my_licenses(query: CallbackQuery):
    licenses = await db.get_license_by_telegram(query.from_user.id)
    if not licenses:
        await send_or_edit(
            query,
            "❌ У тебя пока нет лицензий.\n\nНажми «Купить лицензию» чтобы приобрести.",
            reply_markup=kb_main(is_admin(query.from_user.id)),
        )
        return
    parts = [f"🗂 <b>Твои лицензии ({len(licenses)} шт.):</b>\n"]
    for lic in licenses[:5]:
        parts.append(fmt_license(lic))
        parts.append("")
    await send_or_edit(query, "\n".join(parts), reply_markup=kb_back_main())


# ─── Buy Flow ───────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_buy")
async def cb_menu_buy(query: CallbackQuery):
    lines = ["💳 <b>Выбери тарифный план:</b>\n"]
    for plan_id, plan in PLANS.items():
        if plan.get("admin_only"):
            continue
        price = await db.get_plan_price(plan_id)
        lines.append(
            f"<b>{plan['name']}</b> — <b>${price:.2f} USDT</b>\n"
            f"   {plan['description']}\n"
        )
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
        text = (
            f"📦 <b>{plan['name']}</b> — ${price:.2f} USDT\n\n"
            f"💻 Текущий HWID: <code>{current_hwid}</code>\n\n"
            "Использовать этот HWID или отправь новый:"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Использовать текущий", callback_data=f"use_hwid:{current_hwid}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_buy")],
        ])
        await send_or_edit(query, text, reply_markup=kb)
    else:
        await state.set_state(BuyFlow.waiting_hwid)
        text = (
            f"📦 <b>{PLANS[plan_id]['name']}</b>\n\n"
            "💻 Отправь свой <b>HWID</b> компьютера.\n"
            "Его можно скопировать на экране активации программы."
        )
        await send_or_edit(query, text, reply_markup=kb_back_main())


@dp.callback_query(F.data.startswith("use_hwid:"))
async def cb_use_hwid(query: CallbackQuery, state: FSMContext):
    hwid = query.data.split(":", 1)[1]
    data = await state.get_data()
    await _proceed_to_payment(query, state, hwid, data.get("plan_id", "starter"))


@dp.message(BuyFlow.waiting_hwid)
async def msg_hwid(message: Message, state: FSMContext):
    hwid = message.text.strip().upper() if message.text else ""
    data = await state.get_data()

    if len(hwid) < 8 or " " in hwid:
        await message.answer("❌ Неверный формат HWID. Скопируй его из программы.")
        return

    await db.set_user_hwid(message.from_user.id, hwid)
    await db.upsert_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "")

    if data.get("hwid_only"):
        await state.clear()
        await message.answer(
            f"✅ HWID привязан: <code>{hwid}</code>",
            reply_markup=kb_main(is_admin(message.from_user.id)),
        )
        return

    plan_id = data.get("plan_id", "starter")
    await _proceed_to_payment(message, state, hwid, plan_id)


async def _proceed_to_payment(event, state: FSMContext, hwid: str, plan_id: str):
    plan = PLANS[plan_id]
    price = await db.get_plan_price(plan_id)
    user_id = event.from_user.id if hasattr(event, "from_user") else event.message.from_user.id

    try:
        invoice = await crypto_client.create_invoice(
            amount=price,
            currency="USDT",
            description=f"FMail Sender Pro — {plan['name']}",
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

    await db.save_payment(
        telegram_id=user_id,
        invoice_id=invoice_id,
        plan=plan_id,
        hwid=hwid,
        amount=price,
    )
    await state.update_data(invoice_id=invoice_id, hwid=hwid)
    await state.set_state(BuyFlow.waiting_payment)

    text = (
        f"💳 <b>Оплата</b>\n\n"
        f"📦 Тариф: <b>{plan['name']}</b>\n"
        f"💰 Сумма: <b>${price:.2f} USDT</b>\n"
        f"💻 HWID: <code>{hwid}</code>\n\n"
        f"Нажми <b>«Оплатить»</b> и после оплаты проверь статус."
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
        f"💻 Привязан к HWID: <code>{payment.get('hwid') or 'при первой активации'}</code>"
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
        f"⚙️ <b>Админ-панель</b>\n\n"
        f"📊 Активных лицензий: <b>{stats['active_licenses']}</b>\n"
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
        parts.append(fmt_license(lic))
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
        f"👥 Пользователей: <b>{stats['total_users']}</b>\n"
        f"💰 Выручка: <b>${stats['total_revenue_usdt']:.2f} USDT</b>"
    )
    await send_or_edit(query, text, reply_markup=kb_back_admin())


# ─── Admin Issue Flow ────────────────────────────────────────────────────────
# Порядок: Выбор плана → Telegram ID получателя → HWID → Заметка → Создать

@dp.callback_query(F.data == "admin_issue")
async def cb_admin_issue(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        return
    await state.set_state(AdminFlow.issue_plan)
    await send_or_edit(
        query,
        "🎟 <b>Выдача ключа</b>\n\nВыбери тарифный план:",
        reply_markup=kb_admin_plans(),
    )


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
        f"📨 Отправь <b>Telegram ID</b> получателя (числовой ID)\n"
        f"или <code>-</code> чтобы пропустить:",
        reply_markup=kb_back_admin(),
    )


@dp.message(AdminFlow.issue_telegram_id)
async def msg_admin_telegram_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    raw = message.text.strip() if message.text else ""
    if raw == "-":
        telegram_id = 0
    else:
        try:
            telegram_id = int(raw)
        except ValueError:
            await message.answer("❌ Telegram ID должен быть числом (или <code>-</code> чтобы пропустить).")
            return
    await state.update_data(telegram_id=telegram_id)
    await state.set_state(AdminFlow.issue_hwid)
    await message.answer("💻 Отправь HWID получателя (или <code>-</code> пропустить):")


@dp.message(AdminFlow.issue_hwid)
async def msg_admin_hwid(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    hwid = "" if message.text.strip() == "-" else message.text.strip().upper()
    await state.update_data(hwid=hwid)
    await state.set_state(AdminFlow.issue_note)
    await message.answer("📝 Добавь примечание (или <code>-</code> пропустить):")


@dp.message(AdminFlow.issue_note)
async def msg_admin_note(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    note = "" if message.text.strip() == "-" else message.text.strip()
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

    text = (
        f"✅ <b>Ключ создан!</b>\n\n"
        f"📦 Тариф: <b>{plan.get('name', data['plan_id'])}</b>\n"
        f"💻 HWID: <code>{data.get('hwid') or 'не задан'}</code>\n"
        f"📅 Истекает: <b>{license_data['expires_at'][:10]}</b>\n"
        f"📝 Заметка: {note or '—'}\n\n"
        f"🔑 <b>Ключ:</b>\n<code>{key}</code>"
    )
    await message.answer(text, reply_markup=kb_admin())

    # FIX: Отправляем ключ получателю в Telegram если указан ID
    if telegram_id:
        try:
            recipient_text = (
                f"🎉 <b>Ваш лицензионный ключ FMail Sender Pro</b>\n\n"
                f"📦 Тариф: <b>{plan.get('name', data['plan_id'])}</b>\n"
                f"📅 Действует до: <b>{license_data['expires_at'][:10]}</b>\n\n"
                f"🔑 <b>Ключ:</b>\n<code>{key}</code>\n\n"
                f"Введите его в программе на экране активации."
            )
            await bot.send_message(telegram_id, recipient_text)
            await message.answer(f"✅ Ключ отправлен получателю (ID: <code>{telegram_id}</code>)")
        except Exception as e:
            await message.answer(
                f"⚠️ Не удалось отправить ключ получателю: {e}\n"
                f"Отправьте вручную: <code>{key}</code>"
            )


@dp.callback_query(F.data == "admin_revoke")
async def cb_admin_revoke(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        return
    await state.set_state(AdminFlow.revoke_key)
    await send_or_edit(
        query,
        "🚫 <b>Отзыв ключа</b>\n\nОтправь лицензионный ключ для отзыва:",
        reply_markup=kb_back_admin(),
    )


@dp.message(AdminFlow.revoke_key)
async def msg_admin_revoke(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    key = message.text.strip().upper()
    await state.clear()
    success = await db.revoke_license(key)
    if success:
        await message.answer(f"✅ Ключ <code>{key}</code> отозван.", reply_markup=kb_admin())
    else:
        await message.answer(f"❌ Ключ не найден: <code>{key}</code>", reply_markup=kb_admin())


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
        f"💲 Текущая цена {PLANS[plan_id]['name']}: <b>${current:.2f}</b>\n\nОтправь новую цену в USDT:",
        reply_markup=kb_back_admin(),
    )


@dp.message(AdminFlow.set_price_value)
async def msg_admin_price_value(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        new_price = float(message.text.strip().replace(",", "."))
        if new_price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи корректную цену (например: 25.00)")
        return
    data = await state.get_data()
    plan_id = data["price_plan_id"]
    await db.set_setting(f"price_{plan_id}", str(new_price))
    await state.clear()
    plan = PLANS.get(plan_id, {})
    await message.answer(
        f"✅ Цена <b>{plan.get('name', plan_id)}</b> изменена на <b>${new_price:.2f} USDT</b>",
        reply_markup=kb_admin(),
    )


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
    licenses = await db.get_all_licenses(limit=1000)
    user_ids = list({lic["telegram_id"] for lic in licenses if lic.get("telegram_id")})
    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, text)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await message.answer(
        f"📢 Рассылка завершена\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}",
        reply_markup=kb_admin(),
    )


@dp.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    stats = await db.get_stats()
    text = (
        f"⚙️ <b>Админ-панель</b>\n\n"
        f"📊 Активных лицензий: <b>{stats['active_licenses']}</b>\n"
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

    expires_at = datetime.fromisoformat(lic["expires_at"])
    if datetime.utcnow() > expires_at:
        raise HTTPException(status_code=403, detail="License expired")

    existing_hwid = lic.get("hwid", "")
    if existing_hwid and existing_hwid.upper() != hwid.upper():
        raise HTTPException(status_code=403, detail="HWID mismatch — license bound to another device")

    if not existing_hwid:
        await db.bind_hwid_to_license(key, hwid)

    # FIX: JWT_SECRET импортирован из config — согласован с клиентом (core/license.py)
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


@api_app.get("/health")
async def health():
    return {"status": "ok", "service": "FMail Sender License API"}


# ─── Entry Point ─────────────────────────────────────────────────────────────

async def main():
    await db.init_db()
    logger.info("Starting FMail Sender Bot + API...")

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
