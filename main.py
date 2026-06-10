"""Entry point for Email Sender Pro."""
  import sys
  import os

  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


  def main():
      from core.license import security_check
      security_check()

      from PyQt6.QtWidgets import QApplication
      from PyQt6.QtGui import QFont

      app = QApplication(sys.argv)
      app.setApplicationName("Email Sender Pro")
      app.setApplicationVersion("1.0.0")
      app.setOrganizationName("EmailSenderPro")

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
      container.setWindowTitle("Email Sender Pro — Активация")
      container.setMinimumSize(620, 580)
      container.resize(720, 640)
      container.setStyleSheet(f"background-color: {Colors.BG_BASE};")

      activation = ActivationScreen(hint_message=message)

      def on_success(license_info):
          container.close()
          from gui.app import MainWindow
          window = MainWindow(license_info)
          window.show()

      activation.activation_success.connect(on_success)
      container.setCentralWidget(activation)
      container.show()


  if __name__ == "__main__":
      main()
  