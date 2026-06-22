"""Entry point for FMail Sender Pro."""
import sys
import os

# ── PATCH LOADER ─────────────────────────────────────────────────────────────
# При наличии каталога _patches/ рядом с EXE — грузим оттуда .py-файлы вместо
# встроенных. Это позволяет применять обновления без полной пересборки EXE.
_exe_dir = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
_patch_dir = os.path.join(_exe_dir, "_patches")
if os.path.isdir(_patch_dir) and _patch_dir not in sys.path:
    sys.path.insert(0, _patch_dir)
# ─────────────────────────────────────────────────────────────────────────────

import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core._version import APP_NAME, APP_VERSION


def _check_mode() -> None:
    """Smoke-test: проверяет все импорты и выходит 0 если OK, 1 если ошибка."""
    try:
        from core.sender import SendingEngine
        from core.spam_checker import SpamChecker
        from core.ai_fixer import AiSpamFixer
        from core.warmup import WarmupScheduler
        from core.license import generate_hwid
        print(f"FMailSender v{APP_VERSION} — startup check OK")
        sys.exit(0)
    except Exception as exc:
        print(f"FMailSender startup check FAILED: {exc}", file=sys.stderr)
        sys.exit(1)


def _load_icon(target):
    """Загружает иконку приложения из assets (ICO > PNG)."""
    from PyQt6.QtGui import QIcon
    from pathlib import Path
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    for name in ("fmail_logo.ico", "fmail_logo.png"):
        p = base / "assets" / "images" / name
        if p.exists():
            target.setWindowIcon(QIcon(str(p)))
            return


def _install_global_exception_handler() -> None:
    """Показывает диалог вместо молчаливого краша при любом необработанном исключении."""
    import traceback

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        # Сначала пишем в stderr (видно в логах)
        print(f"[FMailSender] НЕОБРАБОТАННОЕ ИСКЛЮЧЕНИЕ:\n{msg}", file=sys.stderr)
        # Затем пробуем показать QMessageBox если QApplication уже запущен
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance():
                box = QMessageBox()
                box.setWindowTitle("Ошибка приложения")
                box.setIcon(QMessageBox.Icon.Critical)
                box.setText(
                    f"Произошла необработанная ошибка:\n\n"
                    f"<b>{exc_type.__name__}</b>: {exc_value}\n\n"
                    f"Приложение продолжит работу. Подробности в логе."
                )
                box.setDetailedText(msg)
                box.exec()
        except Exception:
            pass

    sys.excepthook = _hook

    # Qt-потоки: перехватываем через threading.excepthook (Python 3.8+)
    import threading

    def _thread_hook(args):
        if args.exc_type and not issubclass(args.exc_type, SystemExit):
            _hook(args.exc_type, args.exc_value, args.exc_traceback)

    threading.excepthook = _thread_hook


def main():
    if "--check" in sys.argv:
        _check_mode()
    if "--version" in sys.argv:
        print(f"FMailSender v{APP_VERSION}")
        sys.exit(0)

    _install_global_exception_handler()

    # Прогрев HWID кэша — запускаем в фоне и ждём завершения до check_license
    from core.license import security_check, generate_hwid
    hwid_ready = threading.Event()

    def _hwid_init():
        generate_hwid()
        hwid_ready.set()

    threading.Thread(target=_hwid_init, daemon=True).start()
    security_check()  # БАГ-4 FIX: синхронно до QApplication — нет race condition с os.abort()

    # Ждём HWID не более 10 сек, чтобы check_license получил актуальный кэш
    hwid_ready.wait(timeout=10.0)

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QFont

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("FTPLabs")

    _load_icon(app)

    from gui.theme import load_fonts, get_stylesheet, Typography
    load_fonts()
    app.setStyleSheet(get_stylesheet())
    font = QFont("Inter")
    font.setPointSize(Typography.SIZE_SM)
    app.setFont(font)

    from core.license import check_license
    valid, license_info, message = check_license()

    if valid and license_info:
        from gui.app import MainWindow
        app._main_window = MainWindow(license_info)
        app._main_window.show()
    else:
        _show_activation_screen(app, message)

    sys.exit(app.exec())


def _show_activation_screen(app, message: str = ""):
    from PyQt6.QtWidgets import QMainWindow
    from gui.screens.screen_activation import ActivationScreen
    from gui.theme import Colors

    container = QMainWindow()
    container.setWindowTitle(f"{APP_NAME} — Активация")
    container.setMinimumSize(560, 520)
    container.resize(680, 620)
    container.setStyleSheet(f"background-color: {Colors.BG_BASE};")
    _load_icon(container)

    activation = ActivationScreen(hint_message=message)

    def on_success(license_info):
        from gui.app import MainWindow
        window = MainWindow(license_info)
        app._main_window = window
        window.show()
        container.close()

    activation.activation_success.connect(on_success)
    container.setCentralWidget(activation)
    container.show()


if __name__ == "__main__":
    main()
