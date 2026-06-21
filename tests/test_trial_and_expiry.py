"""
T012 — тесты защиты триала от повторной выдачи/гонок и логики истечения лицензии.

Чистые тесты без сети: SQLite во временном файле + LicenseInfo.
Запуск: python3 tests/test_trial_and_expiry.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

# Заглушки обязательных env-переменных config.py (только для офлайн-тестов)
os.environ.setdefault("BOT_TOKEN", "test:dummy")
os.environ.setdefault("CRYPTO_BOT_TOKEN", "test-dummy")
os.environ.setdefault("JWT_SECRET", "test-dummy-secret")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)            # core.* (project root)
sys.path.insert(0, os.path.join(_ROOT, "server"))  # config (server-local)

_failures: list[str] = []


def check(cond: bool, label: str) -> None:
    if cond:
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label}")
        _failures.append(label)


# ── Триал: атомарный захват, защита от гонок и откат ────────────────────────

async def _trial_suite() -> None:
    import database

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    database.DB_PATH = tmp.name
    try:
        await database.init_db()

        uid = 4242

        # 8 параллельных попыток взять триал — ровно одна должна выиграть
        results = await asyncio.gather(*[database.try_claim_trial(uid) for _ in range(8)])
        wins = sum(1 for r in results if r)
        check(wins == 1, f"параллельный захват триала: ровно 1 победитель (получено {wins})")

        # Повторная попытка после захвата — отказ
        again = await database.try_claim_trial(uid)
        check(again is False, "повторный захват триала отклонён")

        # Откат флага позволяет повторить (сценарий: выдача лицензии не удалась)
        await database.release_trial(uid)
        after_release = await database.try_claim_trial(uid)
        check(after_release is True, "после release_trial триал снова доступен")

        # Другой пользователь не затронут
        other = await database.try_claim_trial(9999)
        check(other is True, "независимый пользователь получает свой триал")
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


# ── Лицензия: логика is_expired ─────────────────────────────────────────────

def _expiry_suite() -> None:
    from core.license import LicenseInfo

    now = datetime.now(timezone.utc)
    past = int((now - timedelta(hours=1)).timestamp())
    future = int((now + timedelta(days=3)).timestamp())

    expired = LicenseInfo({"plan": "trial", "exp": past})
    check(expired.is_expired is True, "истёкшая лицензия → is_expired=True")
    check(expired.days_left == 0, "истёкшая лицензия → days_left=0")

    active = LicenseInfo({"plan": "pro", "exp": future})
    check(active.is_expired is False, "активная лицензия → is_expired=False")
    check(active.days_left >= 2, "активная лицензия → days_left>=2")

    # exp=0 трактуется как бессрочная (дата 2099)
    perpetual = LicenseInfo({"plan": "pro", "exp": 0})
    check(perpetual.is_expired is False, "exp=0 → не истекла (бессрочная)")


def main() -> int:
    asyncio.run(_trial_suite())
    _expiry_suite()
    print()
    if _failures:
        print(f"FAILED: {len(_failures)} — " + "; ".join(_failures))
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
