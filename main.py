"""
FMailSender — Entry point v7.0.0
=================================
Запускает uvicorn с FastAPI-сервером.

Изменения v7.0.0:
  - Все stderr/stdout перенаправляются в startup.log (читается Tauri при ошибке)
  - --test флаг: быстрая проверка импортов без запуска uvicorn (для CI)
  - Улучшенный try/except на старте: все ошибки пишутся в лог до краша
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

# ── Startup log (Tauri читает его при ошибке запуска) ────────────────────────

def _get_startup_log_path() -> Path:
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        log_dir = Path(appdata) / "FMailSender"
    else:
        log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "startup.log"


_STARTUP_LOG = _get_startup_log_path()


def _setup_startup_logging() -> None:
    """Настраивает логирование в startup.log и консоль."""
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers: list[logging.Handler] = []

    # File handler (для Tauri)
    try:
        fh = logging.FileHandler(str(_STARTUP_LOG), mode="w", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(fmt))
        handlers.append(fh)
    except Exception:
        pass

    # Stream handler (для консоли / subprocess capture)
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.INFO)
    sh.setFormatter(logging.Formatter(fmt))
    handlers.append(sh)

    logging.basicConfig(level=logging.DEBUG, handlers=handlers, force=True)


_setup_startup_logging()
logger = logging.getLogger("fmail.main")

# ── --test mode (CI build verification) ──────────────────────────────────────

if "--test" in sys.argv:
    # Быстрая проверка импортов без запуска uvicorn
    logger.info("--test mode: checking imports...")
    try:
        import fastapi          # noqa: F401
        import uvicorn          # noqa: F401
        import aiosmtplib       # noqa: F401
        import cryptography     # noqa: F401
        import requests         # noqa: F401
        from core.server import app  # noqa: F401
        logger.info("All imports OK — test passed")
        sys.exit(0)
    except Exception as exc:
        logger.critical("Import test FAILED: %s", exc, exc_info=True)
        sys.exit(1)

# ── Normal startup ────────────────────────────────────────────────────────────

def main() -> None:
    from core._version import APP_VERSION
    logger.info("FMailSender core v%s starting...", APP_VERSION)

    try:
        # Импортируем приложение (FastAPI)
        logger.info("Loading FastAPI application...")
        from core.server import app
        logger.info("FastAPI app loaded OK")

        # Запускаем uvicorn
        import uvicorn
        logger.info("Starting uvicorn on 127.0.0.1:7531")
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=7531,
            log_level="warning",
            access_log=False,
            reload=False,
            workers=1,
        )

    except ImportError as exc:
        logger.critical(
            "Import error — возможно, отсутствует зависимость: %s\n"
            "Это PyInstaller-сборка? Проверьте hiddenimports в fmail-core.spec.",
            exc,
            exc_info=True,
        )
        sys.exit(1)

    except OSError as exc:
        if "10048" in str(exc) or "Address already in use" in str(exc):
            logger.critical(
                "Порт 7531 уже занят. Закройте другой экземпляр FMailSender."
            )
        else:
            logger.critical("OS error: %s", exc, exc_info=True)
        sys.exit(1)

    except Exception as exc:
        logger.critical("Неожиданная ошибка при запуске: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
