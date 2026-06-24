#!/usr/bin/env python3
"""
Bot Handler Checker — статическая проверка регистрации хендлеров бота.
Запуск: python3 scripts/bot_checker.py
Используется в CI/CD после каждого деплоя на сервер.
"""
import sys
from pathlib import Path

BOT_FILE = Path(__file__).parent.parent / "server" / "bot.py"

# Все callback_data-паттерны, которые должны быть зарегистрированы
EXPECTED_CALLBACKS = [
    "buy_plan", "check_license", "my_balance", "open_ticket", "main_menu",
    "admin_panel", "admin_stats", "admin_broadcast", "admin_licenses",
    "admin_add_lic", "admin_revoke_lic", "admin_promos", "admin_promo_create",
    "admin_promo_deactivate", "admin_balance", "admin_mods", "admin_tickets",
    "promo_yes", "promo_no", "sub_check", "cancel_ticket",
    "pay_balance:", "check_pay:", "pay_crypto:", "pay_xrocket:",
    "admin_ticket:", "admin_reply:", "admin_remove_mod:", "admin_set_price",
]

# Команды бота (без слеша)
EXPECTED_COMMANDS = ["start", "help", "check", "buy", "balance", "ticket", "cancel"]

# Критические async-функции
CRITICAL_FUNCTIONS = [
    "async def cmd_start",
    "async def cb_buy_plan",
    "async def cb_admin_panel",
    "async def cb_check_pay",
    "async def cb_pay_balance",
    "async def cb_admin_promos",
    "async def cb_admin_balance",
]

# FSM State классы
FSM_CLASSES = ["AdminFlow", "UserFlow", "SupportFlow"]

errors = []
warnings = []

try:
    source = BOT_FILE.read_text(encoding="utf-8")
except FileNotFoundError:
    print(f"❌ КРИТИЧНО: {BOT_FILE} не найден!")
    sys.exit(1)

# --- Проверяем команды ---
for cmd in EXPECTED_COMMANDS:
    patterns = [
        f'Command("{cmd}")', f"Command('{cmd}')",
        f'commands=["{cmd}"', f"commands=['{cmd}'",
        f'"/{cmd}"', f"'/{cmd}'",
    ]
    if not any(p in source for p in patterns):
        errors.append(f"❌ Команда /{cmd} не зарегистрирована в bot.py")

# --- Проверяем callbacks ---
for cb in EXPECTED_CALLBACKS:
    if cb not in source:
        errors.append(f"❌ callback_data='{cb}' НЕ найден в bot.py")

# --- Проверяем критические функции ---
for fn in CRITICAL_FUNCTIONS:
    if fn not in source:
        errors.append(f"❌ Критическая функция '{fn}' не найдена")

# --- Проверяем FSM state классы ---
for state in FSM_CLASSES:
    if state not in source:
        warnings.append(f"⚠️  FSM class '{state}' не найден — возможная регрессия")

# --- Проверяем что admin-only проверки есть ---
if "is_admin" not in source:
    errors.append("❌ Функция is_admin() не найдена — admin panel незащищена!")

# --- Проверяем payment провайдеры ---
for provider in ["crypto_client", "xrocket_client"]:
    if provider not in source:
        warnings.append(f"⚠️  {provider} не найден — провайдер не подключён")

# --- Проверяем что нет print() в production коде ---
import ast
try:
    tree = ast.parse(source)
    print_calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "print"
    ]
    if print_calls:
        warnings.append(f"⚠️  Найдено {len(print_calls)} вызовов print() в bot.py (используй logger)")
except SyntaxError as e:
    errors.append(f"❌ SyntaxError в bot.py: {e}")

# --- Итоговый отчёт ---
print("=" * 62)
print("  Bot Handler Checker — FMailSender")
print("=" * 62)

if not errors and not warnings:
    print(f"\n✅ Все проверки пройдены!")
    print(f"   Callbacks: {len(EXPECTED_CALLBACKS)} — все OK")
    print(f"   Команды: {len(EXPECTED_COMMANDS)} — все OK")
    print(f"   Критические функции: {len(CRITICAL_FUNCTIONS)} — все OK")
    print(f"   FSM states: {len(FSM_CLASSES)} — все OK")
    print("\n🚀 Бот готов к работе!")
else:
    if errors:
        print(f"\n❌ БЛОКЕРЫ ({len(errors)}):")
        for e in errors:
            print(f"   {e}")
    if warnings:
        print(f"\n⚠️  Предупреждения ({len(warnings)}):")
        for w in warnings:
            print(f"   {w}")

    if any(e.startswith("❌") for e in errors):
        print("\n⛔ Деплой не рекомендован до исправления блокеров!")

sys.exit(1 if any(e.startswith("❌") for e in errors) else 0)
