"""Entry point for FMail Sender Pro."""
  import sys
  import os

  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

  from core._version import APP_NAME, APP_VERSION


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


  def main():
      from core.license import security_check
      security_check()

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
          # Сохраняем ссылку на уровне app — предотвращает GC уничтожение окна
          app._main_window = window
          window.show()
          container.close()

      activation.activation_success.connect(on_success)
      container.setCentralWidget(activation)
      container.show()


  if __name__ == "__main__":
      main()
  