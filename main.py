"""
Точка входа Email Sender Pro.
Проверка лицензии, anti-debug, запуск GUI.
"""
import sys
import os

# Добавляем директорию проекта в sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    # ── Проверка безопасности ─────────────────
    from core.license import security_check
    security_check()

    # ── Инициализация Qt ─────────────────────
    from PyQt6.QtWidgets import QApplication, QSplashScreen
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QPixmap, QColor, QFont

    app = QApplication(sys.argv)
    app.setApplicationName("Email Sender Pro")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("EmailSenderPro")

    # Загружаем шрифты и стили
    from gui.theme import load_fonts, get_stylesheet, Colors, Typography
    load_fonts()
    app.setStyleSheet(get_stylesheet())
    font = QFont("Inter")
    font.setPointSize(Typography.SIZE_SM)
    app.setFont(font)

    # ── Проверка активации ───────────────────
    from core.license import check_license, is_activated

    valid, license_info, message = check_license()

    if valid and license_info:
        # Лицензия активна — запускаем главное окно
        from gui.app import MainWindow
        window = MainWindow(license_info)
        window.show()
    else:
        # Нужна активация — показываем экран активации
        _show_activation_screen(app, message)

    sys.exit(app.exec())


def _show_activation_screen(app, message: str = ""):
    """Показывает экран активации и переходит на главный экран после успеха."""
    from PyQt6.QtWidgets import QMainWindow, QWidget
    from PyQt6.QtCore import QSize
    from gui.screens.screen_activation import ActivationScreen
    from gui.theme import Colors

    container = QMainWindow()
    container.setWindowTitle("Email Sender Pro — Активация")
    container.setMinimumSize(600, 500)
    container.resize(700, 600)
    container.setStyleSheet(f"background-color: {Colors.BG_BASE};")

    activation = ActivationScreen()

    def on_activation_success(license_info):
        container.close()
        from gui.app import MainWindow
        window = MainWindow(license_info)
        window.show()

    activation.activation_success.connect(on_activation_success)
    container.setCentralWidget(activation)
    container.show()


if __name__ == "__main__":
    main()
