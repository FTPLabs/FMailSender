"""Entry point for Email Sender Pro."""
  import sys
  import os
  import threading

  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

  APP_VERSION = "1.0.0"


  def _run_update_check(app, parent_window):
      """Check for updates in background; show dialog on main thread if found."""
      try:
          from core.updater import check_for_updates
          info = check_for_updates(current_version=APP_VERSION)
          if info:
              from PyQt6.QtCore import QTimer
              from gui.dialogs.dialog_update import UpdateDialog

              def show_dialog():
                  dlg = UpdateDialog(info, parent=parent_window)
                  dlg.exec()

              QTimer.singleShot(2000, show_dialog)  # 2s delay after startup
      except Exception as e:
          import logging
          logging.getLogger("updater").debug(f"Update check error: {e}")


  def main():
      from core.license import security_check
      security_check()

      from PyQt6.QtWidgets import QApplication
      from PyQt6.QtGui import QFont

      app = QApplication(sys.argv)
      app.setApplicationName("Email Sender Pro")
      app.setApplicationVersion(APP_VERSION)
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
          # Start background update check after window is shown
          threading.Thread(
              target=_run_update_check, args=(app, window), daemon=True
          ).start()
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
          from gui.dialogs.dialog_update import UpdateDialog
          window = MainWindow(license_info)
          window.show()
          threading.Thread(
              target=_run_update_check, args=(app, window), daemon=True
          ).start()

      activation.activation_success.connect(on_success)
      container.setCentralWidget(activation)
      container.show()


  if __name__ == "__main__":
      main()
  