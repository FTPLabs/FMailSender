"""
Тест атомарной выдачи лицензии по оплате (защита от double-credit).

Проверяет гонку «ручная проверка vs фоновый поллер»: при множестве
параллельных вызовов create_license_for_payment для одного invoice_id
должна быть создана РОВНО ОДНА лицензия, ровно один вызов вернёт
created=True, остальные — created=False с тем же ключом.

Чистый тест без сети: SQLite во временном файле.
Запуск: python3 tests/test_payment_concurrency.py
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
import tempfile

# Заглушки обязательных env-переменных config.py (только для офлайн-тестов)
os.environ.setdefault("BOT_TOKEN", "test:dummy")
os.environ.setdefault("CRYPTO_BOT_TOKEN", "test-dummy")
os.environ.setdefault("JWT_SECRET", "test-dummy-secret")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "server"))

_failures: list[str] = []


def check(cond: bool, label: str) -> None:
    if cond:
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label}")
        _failures.append(label)


async def _suite() -> None:
    import database

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    database.DB_PATH = tmp.name
    try:
        await database.init_db()

        uid = 7777
        invoice_id = "xrocket:999001"
        plan = "week"

        await database.save_payment(
            telegram_id=uid, invoice_id=invoice_id, plan=plan, hwid="",
            amount=7.5, currency="USDT", provider="xrocket",
        )

        # 12 параллельных попыток выдать лицензию по одному платежу
        results = await asyncio.gather(
            *[database.create_license_for_payment(
                invoice_id=invoice_id, plan=plan, telegram_id=uid, hwid="",
            ) for _ in range(12)]
        )

        created_true = [r for r in results if r.get("created")]
        keys = {r.get("key") for r in results if r.get("key")}

        check(len(created_true) == 1, f"ровно один вызов вернул created=True (получено {len(created_true)})")
        check(len(keys) == 1, f"все вызовы вернули один и тот же ключ (уникальных ключей: {len(keys)})")
        check(bool(created_true) and bool(created_true[0].get("key")),
              "победитель вернул непустой лицензионный ключ")

        # В БД должна быть ровно одна лицензия для пользователя
        con = sqlite3.connect(tmp.name)
        try:
            lic_count = con.execute(
                "SELECT COUNT(*) FROM licenses WHERE telegram_id=?", (uid,)
            ).fetchone()[0]
            pay_row = con.execute(
                "SELECT status, license_key FROM payments WHERE invoice_id=?", (invoice_id,)
            ).fetchone()
        finally:
            con.close()

        check(lic_count == 1, f"в БД ровно одна лицензия (найдено {lic_count})")
        check(pay_row is not None and pay_row[0] == "paid", "платёж помечен paid")
        check(pay_row is not None and pay_row[1] == created_true[0].get("key"),
              "license_key платежа совпадает с выданным ключом")

        # Повторный вызов после завершения — идемпотентен (created=False, тот же ключ)
        again = await database.create_license_for_payment(
            invoice_id=invoice_id, plan=plan, telegram_id=uid, hwid="",
        )
        check(again.get("created") is False, "повторная выдача идемпотентна (created=False)")
        check(again.get("key") == created_true[0].get("key"), "идемпотентный вызов вернул тот же ключ")

        con = sqlite3.connect(tmp.name)
        try:
            lic_count2 = con.execute(
                "SELECT COUNT(*) FROM licenses WHERE telegram_id=?", (uid,)
            ).fetchone()[0]
        finally:
            con.close()
        check(lic_count2 == 1, f"после повторного вызова лицензия всё ещё одна (найдено {lic_count2})")
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def main() -> int:
    asyncio.run(_suite())
    if _failures:
        print(f"\n{len(_failures)} TEST(S) FAILED")
        return 1
    print("\nALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
