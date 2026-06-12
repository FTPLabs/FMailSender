"""Entry point for FMail Sender."""
import sys
import os
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core._version import APP_NAME, APP_VERSION


def _run_update_check_disabled():
    """
    Автоматическое обновление отключено согласно правилам площадки (п. 1.8).
    Новые версии публикуются отдельно для свободного скачивания.
    """
    pass


def main():
    from core.license import security_check
    security_check()

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QFont

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("FTPLabs")

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
        window = MainWindow(license_info)
        window.show()
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

    activation = ActivationScreen(hint_message=message)

    def on_success(license_info):
        from gui.app import MainWindow
        window = MainWindow(license_info)
        # Сохраняем ссылку до закрытия контейнера, иначе GC уничтожит окно
        app._main_window = window
        window.show()
        container.close()

    activation.activation_success.connect(on_success)
    container.setCentralWidget(activation)
    container.show()


if __name__ == "__main__":
    main()
