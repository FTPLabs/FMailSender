"""
  Update dialog: shows release notes, download progress bar, and action buttons.
  """
  import tempfile
  from pathlib import Path

  from PyQt6.QtWidgets import (
      QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
      QProgressBar, QTextEdit, QFrame
  )
  from PyQt6.QtCore import Qt, QTimer, pyqtSignal
  from PyQt6.QtGui import QDesktopServices
  from PyQt6.QtCore import QUrl

  from core.updater import UpdateInfo, Downloader, apply_update_windows, open_download_folder
  from gui.theme import Colors, Spacing


  def _fmt_size(b: int) -> str:
      if b >= 1_048_576:
          return f"{b / 1_048_576:.1f} МБ"
      if b >= 1024:
          return f"{b / 1024:.0f} КБ"
      return f"{b} Б"


  class UpdateDialog(QDialog):
      """
      Shows available update info and handles download + apply flow.
      """
      restart_requested = pyqtSignal()

      def __init__(self, update_info: UpdateInfo, parent=None):
          super().__init__(parent)
          self._info = update_info
          self._downloader: Downloader | None = None
          self._zip_path: Path | None = None
          self._temp_dir = Path(tempfile.mkdtemp(prefix="esp_update_"))
          self.setWindowTitle(f"Доступно обновление — v{update_info.version}")
          self.setMinimumWidth(520)
          self.setMinimumHeight(420)
          self.setModal(True)
          self._setup_ui()

      def _setup_ui(self):
          layout = QVBoxLayout(self)
          layout.setSpacing(Spacing.LG)
          layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)

          # Header
          header_row = QHBoxLayout()
          icon_lbl = QLabel("🚀")
          icon_lbl.setStyleSheet("font-size:28px;")
          header_row.addWidget(icon_lbl)
          vbox = QVBoxLayout()
          title = QLabel(f"Email Sender Pro v{self._info.version}")
          title.setObjectName("label_title")
          title.setStyleSheet(f"font-size:20px;font-weight:bold;color:{Colors.TEXT_PRIMARY};")
          vbox.addWidget(title)
          sub = QLabel(self._info.release_name)
          sub.setObjectName("label_muted")
          vbox.addWidget(sub)
          header_row.addLayout(vbox)
          header_row.addStretch()
          layout.addLayout(header_row)

          # Meta row
          meta_frame = QFrame()
          meta_frame.setObjectName("card")
          meta_layout = QHBoxLayout(meta_frame)
          meta_layout.setContentsMargins(12, 8, 12, 8)

          size_lbl = QLabel(
              f"📦  Размер: {_fmt_size(self._info.download_size)}"
              if self._info.download_size else "📦  Обновление доступно"
          )
          size_lbl.setObjectName("label_muted")
          meta_layout.addWidget(size_lbl)
          meta_layout.addStretch()

          published = self._info.published_at[:10] if self._info.published_at else ""
          if published:
              date_lbl = QLabel(f"📅  {published}")
              date_lbl.setObjectName("label_muted")
              meta_layout.addWidget(date_lbl)

          layout.addWidget(meta_frame)

          # Release notes
          notes_lbl = QLabel("Что нового:")
          notes_lbl.setObjectName("label_muted")
          layout.addWidget(notes_lbl)

          self.notes_view = QTextEdit()
          self.notes_view.setReadOnly(True)
          self.notes_view.setMarkdown(self._info.body or "_Нет описания_")
          self.notes_view.setMaximumHeight(140)
          layout.addWidget(self.notes_view)

          # Progress
          self.progress_label = QLabel("")
          self.progress_label.setObjectName("label_muted")
          self.progress_label.setVisible(False)
          layout.addWidget(self.progress_label)

          self.progress_bar = QProgressBar()
          self.progress_bar.setRange(0, 100)
          self.progress_bar.setValue(0)
          self.progress_bar.setObjectName("activation_bar")
          self.progress_bar.setVisible(False)
          layout.addWidget(self.progress_bar)

          self.status_label = QLabel("")
          self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
          self.status_label.setWordWrap(True)
          self.status_label.setVisible(False)
          layout.addWidget(self.status_label)

          layout.addStretch()

          # Buttons
          btn_row = QHBoxLayout()
          self.skip_btn = QPushButton("Пропустить")
          self.skip_btn.clicked.connect(self.reject)
          btn_row.addWidget(self.skip_btn)
          btn_row.addStretch()

          self.open_btn = QPushButton("Открыть в браузере")
          self.open_btn.clicked.connect(self._open_browser)
          btn_row.addWidget(self.open_btn)

          self.download_btn = QPushButton("⬇  Скачать и установить")
          self.download_btn.setObjectName("btn_primary")
          self.download_btn.setFixedHeight(40)
          self.download_btn.clicked.connect(self._start_download)
          btn_row.addWidget(self.download_btn)

          layout.addLayout(btn_row)

      def _open_browser(self):
          url = f"https://github.com/FTPLabs/EmailSenderPro/releases/tag/{self._info.tag}"
          QDesktopServices.openUrl(QUrl(url))

      def _start_download(self):
          self.download_btn.setEnabled(False)
          self.download_btn.setText("Загрузка...")
          self.skip_btn.setText("Отмена")
          self.skip_btn.clicked.disconnect()
          self.skip_btn.clicked.connect(self._cancel_download)
          self.open_btn.setVisible(False)
          self.progress_bar.setVisible(True)
          self.progress_label.setVisible(True)
          self.status_label.setVisible(True)
          self.progress_label.setText("Подготовка к загрузке...")

          self._downloader = Downloader(
              url=self._info.download_url,
              dest_dir=self._temp_dir,
              progress_callback=self._on_progress,
              finished_callback=self._on_finished,
          )
          self._downloader.start()

      def _cancel_download(self):
          if self._downloader:
              self._downloader.cancel()
          self.reject()

      def _on_progress(self, downloaded: int, total: int):
          def update():
              if total > 0:
                  pct = int(downloaded / total * 100)
                  self.progress_bar.setValue(pct)
                  self.progress_label.setText(
                      f"Загружено: {_fmt_size(downloaded)} / {_fmt_size(total)}  ({pct}%)"
                  )
              else:
                  self.progress_label.setText(f"Загружено: {_fmt_size(downloaded)}")
          QTimer.singleShot(0, update)

      def _on_finished(self, zip_path, error: str | None):
          def update():
              if error:
                  self.progress_bar.setValue(0)
                  self.status_label.setText(f"Ошибка загрузки: {error}")
                  self.status_label.setStyleSheet(f"color:{Colors.ERROR};")
                  self.download_btn.setText("Повторить")
                  self.download_btn.setEnabled(True)
                  self.download_btn.clicked.disconnect()
                  self.download_btn.clicked.connect(self._start_download)
                  self.skip_btn.setText("Закрыть")
                  self.skip_btn.clicked.disconnect()
                  self.skip_btn.clicked.connect(self.reject)
                  return

              self._zip_path = zip_path
              self.progress_bar.setValue(100)
              self.progress_label.setText(f"Загружено: {_fmt_size(self._info.download_size)}")
              self._apply_update()

          QTimer.singleShot(0, update)

      def _apply_update(self):
          import platform
          if platform.system() == "Windows":
              self.status_label.setText(
                  "Применение обновления...\nПриложение перезапустится автоматически."
              )
              self.status_label.setStyleSheet(f"color:{Colors.SUCCESS};")
              ok = apply_update_windows(self._zip_path)
              if ok:
                  self.download_btn.setText("Готово — закрытие...")
                  self.download_btn.setEnabled(False)
                  self.skip_btn.setVisible(False)
                  QTimer.singleShot(1500, self._do_restart)
              else:
                  self._fallback_open()
          else:
              self._fallback_open()

      def _fallback_open(self):
          """When auto-apply is not available, open the download folder."""
          self.status_label.setText("Откройте папку загрузки и установите обновление вручную.")
          self.status_label.setStyleSheet(f"color:{Colors.WARNING};")
          if self._zip_path:
              open_download_folder(self._zip_path)
          self.download_btn.setText("Открыть папку")
          self.download_btn.setEnabled(True)
          self.download_btn.clicked.disconnect()
          self.download_btn.clicked.connect(
              lambda: open_download_folder(self._zip_path) if self._zip_path else None
          )

      def _do_restart(self):
          self.restart_requested.emit()
          self.accept()
          import sys
          sys.exit(0)

      def closeEvent(self, event):
          if self._downloader and self._downloader.is_alive():
              self._downloader.cancel()
          super().closeEvent(event)
  