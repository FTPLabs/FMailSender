"""
UpdateDialog v2.0 — показывает информацию о релизе, предпочитает patch-обновление.
Patch-режим: скачивает только изменённые файлы (~КБ) вместо полного EXE (~МБ).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QFrame
)
from PyQt6.QtCore import QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl

from core.updater import (
    UpdateInfo, Downloader, apply_update_windows,
    fetch_patch_manifest, apply_patch,
)
from gui.theme import Colors, Spacing
from gui import icons


def _fmt_size(b: int) -> str:
    if b >= 1_048_576:
        return f"{b / 1_048_576:.1f} МБ"
    if b >= 1024:
        return f"{b / 1024:.0f} КБ"
    return f"{b} Б"


class UpdateDialog(QDialog):
    """
    Диалог обновления с поддержкой patch-режима.
    """
    restart_requested = pyqtSignal()

    def __init__(self, update_info: UpdateInfo, parent=None):
        super().__init__(parent)
        self._info = update_info
        self._downloader: Downloader | None = None
        self._zip_path: Path | None = None
        self._temp_dir = Path(tempfile.mkdtemp(prefix="fms_update_"))
        self._patch_mode = False  # True = скачиваем только патч
        self.setWindowTitle(f"Доступно обновление — v{update_info.version}")
        self.setMinimumWidth(520)
        self.setMinimumHeight(440)
        self.setModal(True)
        self._setup_ui()
        # Загружаем patch manifest в фоне
        QTimer.singleShot(100, self._load_patch_manifest)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(Spacing.LG)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)

        # Заголовок
        header_row = QHBoxLayout()
        icon_lbl = QLabel()
        icon_lbl.setPixmap(
            icons.make_icon(icons.ROCKET, color=Colors.ACCENT).pixmap(QSize(28, 28))
        )
        header_row.addWidget(icon_lbl)
        vbox = QVBoxLayout()
        title = QLabel(f"FMail Sender v{self._info.version}")
        title.setStyleSheet(f"font-size:20px;font-weight:bold;color:{Colors.TEXT_PRIMARY};")
        vbox.addWidget(title)
        self._sub_lbl = QLabel(self._info.release_name)
        self._sub_lbl.setObjectName("label_muted")
        vbox.addWidget(self._sub_lbl)
        header_row.addLayout(vbox)
        header_row.addStretch()
        layout.addLayout(header_row)

        # Мета-строка (размер + дата)
        meta_frame = QFrame()
        meta_frame.setObjectName("card")
        meta_layout = QHBoxLayout(meta_frame)
        meta_layout.setContentsMargins(12, 8, 12, 8)

        size_icon = QLabel()
        size_icon.setPixmap(icons.make_icon(icons.PACKAGE).pixmap(QSize(16, 16)))
        meta_layout.addWidget(size_icon)
        self._size_lbl = QLabel(
            f"Полный EXE: {_fmt_size(self._info.download_size)}"
            if self._info.download_size else "Обновление доступно"
        )
        self._size_lbl.setObjectName("label_muted")
        meta_layout.addWidget(self._size_lbl)
        meta_layout.addStretch()

        published = self._info.published_at[:10] if self._info.published_at else ""
        if published:
            date_icon = QLabel()
            date_icon.setPixmap(icons.make_icon(icons.CALENDAR).pixmap(QSize(16, 16)))
            meta_layout.addWidget(date_icon)
            date_lbl = QLabel(f"{published}")
            date_lbl.setObjectName("label_muted")
            meta_layout.addWidget(date_lbl)

        layout.addWidget(meta_frame)

        # Patch-badge (скрыт до загрузки манифеста)
        patch_row = QHBoxLayout()
        patch_row.setContentsMargins(0, 4, 0, 4)
        self._patch_badge_icon = QLabel()
        self._patch_badge_icon.setPixmap(
            icons.make_icon(icons.ZAP, color="#22c55e").pixmap(QSize(16, 16))
        )
        self._patch_badge_icon.setVisible(False)
        patch_row.addWidget(self._patch_badge_icon)
        self._patch_badge = QLabel("")
        self._patch_badge.setStyleSheet(
            f"color: #22c55e; font-weight:bold; font-size:13px;"
        )
        self._patch_badge.setVisible(False)
        patch_row.addWidget(self._patch_badge)
        patch_row.addStretch()
        layout.addLayout(patch_row)

        # Заметки о релизе
        notes_lbl = QLabel("Что нового:")
        notes_lbl.setStyleSheet(f"font-weight:bold;color:{Colors.TEXT_PRIMARY};")
        layout.addWidget(notes_lbl)

        self._notes = QTextEdit()
        self._notes.setReadOnly(True)
        self._notes.setMaximumHeight(130)
        body = self._info.body or "Подробности на странице релиза."
        self._notes.setPlainText(body)
        layout.addWidget(self._notes)

        # Прогресс-бар
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setRange(0, 100)
        layout.addWidget(self._progress)

        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("label_muted")
        self._status_lbl.setVisible(False)
        layout.addWidget(self._status_lbl)

        # Кнопки
        btn_row = QHBoxLayout()
        self._btn_later = QPushButton("Напомнить позже")
        self._btn_later.setObjectName("btn_secondary")
        self._btn_later.clicked.connect(self.reject)
        btn_row.addWidget(self._btn_later)
        btn_row.addStretch()

        self._btn_open = QPushButton("Открыть страницу")
        self._btn_open.setObjectName("btn_secondary")
        self._btn_open.clicked.connect(self._open_release_page)
        btn_row.addWidget(self._btn_open)

        self._btn_update = QPushButton("Обновить")
        self._btn_update.setObjectName("btn_primary")
        self._btn_update.setIcon(icons.make_icon(icons.DOWNLOAD))
        self._btn_update.setIconSize(QSize(16, 16))
        self._btn_update.clicked.connect(self._start_update)
        btn_row.addWidget(self._btn_update)

        layout.addLayout(btn_row)

    # ── Patch manifest ────────────────────────────────────────────────────────

    def _load_patch_manifest(self):
        """Загружает patch manifest в фоновом потоке."""
        import threading
        def _worker():
            ok = fetch_patch_manifest(self._info)
            if ok:
                from PyQt6.QtCore import QMetaObject, Q_ARG
                QTimer.singleShot(0, self._on_patch_ready)
        threading.Thread(target=_worker, daemon=True).start()

    def _on_patch_ready(self):
        """Вызывается из главного потока когда patch manifest загружен."""
        if not self._info.is_patch_available:
            return
        patch_kb = self._info.patch_size / 1024
        full_mb = self._info.download_size / 1_048_576 if self._info.download_size else 0
        
        badge_text = f"Доступен быстрый патч: ~{patch_kb:.0f} КБ"
        if full_mb:
            badge_text += f" (вместо {full_mb:.0f} МБ полного EXE)"
        
        self._patch_badge.setText(badge_text)
        self._patch_badge.setVisible(True)
        self._patch_badge_icon.setVisible(True)
        self._btn_update.setText("Применить патч")
        self._btn_update.setIcon(icons.make_icon(icons.ZAP))
        self._btn_update.setIconSize(QSize(16, 16))
        self._patch_mode = True
        self.adjustSize()

    # ── Обновление ───────────────────────────────────────────────────────────

    def _start_update(self):
        self._btn_update.setEnabled(False)
        self._btn_later.setEnabled(False)
        self._btn_open.setEnabled(False)
        self._progress.setVisible(True)
        self._status_lbl.setVisible(True)

        if self._patch_mode and self._info.is_patch_available:
            self._start_patch_update()
        else:
            self._start_full_update()

    def _start_patch_update(self):
        """Скачивает только изменённые .py файлы и применяет патч."""
        import threading

        self._status_lbl.setText("Применение патча...")
        total = len(self._info.patch_files)
        self._progress.setRange(0, total)
        self._progress.setValue(0)

        def _on_progress(current: int, tot: int, filename: str):
            QTimer.singleShot(0, lambda: (
                self._progress.setValue(current),
                self._status_lbl.setText(f"Загрузка: {Path(filename).name}"),
            ))

        def _worker():
            ok, err = apply_patch(self._info.patch_files, on_progress=_on_progress)
            QTimer.singleShot(0, lambda: self._on_patch_done(ok, err))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_patch_done(self, ok: bool, err: str):
        self._progress.setValue(self._progress.maximum())
        if ok:
            n = len(self._info.patch_files)
            self._status_lbl.setText(
                f"Патч применён ({n} файл{'ов' if n != 1 else ''}). Перезапустите приложение."
            )
            self._status_lbl.setStyleSheet("color: #22c55e; font-weight:bold;")
            self._btn_update.setText("Перезапустить")
            self._btn_update.setIcon(icons.make_icon(icons.REFRESH))
            self._btn_update.setIconSize(QSize(16, 16))
            self._btn_update.setEnabled(True)
            self._btn_update.clicked.disconnect()
            self._btn_update.clicked.connect(self._request_restart)
        else:
            self._status_lbl.setText(f"Ошибка патча: {err}")
            self._status_lbl.setStyleSheet("color: #ef4444;")
            self._btn_update.setText("Повторить")
            self._btn_update.setEnabled(True)

    def _start_full_update(self):
        """Скачивает полный EXE и применяет его."""
        dest = self._temp_dir / f"FMailSender_{self._info.version}.exe"
        self._zip_path = dest
        self._status_lbl.setText("Загрузка обновления...")
        self._progress.setRange(0, 100)

        def _on_progress(done: int, total: int):
            pct = int(done / total * 100) if total > 0 else 0
            size_str = f"{_fmt_size(done)} / {_fmt_size(total)}" if total else _fmt_size(done)
            QTimer.singleShot(0, lambda: (
                self._progress.setValue(pct),
                self._status_lbl.setText(f"Загрузка: {size_str}"),
            ))

        def _on_done(ok: bool, err: str):
            QTimer.singleShot(0, lambda: self._on_download_done(ok, err))

        self._downloader = Downloader(
            self._info.download_url, dest,
            on_progress=_on_progress, on_done=_on_done,
        )
        self._downloader.start()

    def _on_download_done(self, ok: bool, err: str):
        if ok and self._zip_path and self._zip_path.exists():
            self._status_lbl.setText("Загрузка завершена. Применение...")
            self._status_lbl.setStyleSheet("color: #22c55e; font-weight:bold;")
            QTimer.singleShot(500, lambda: apply_update_windows(self._zip_path))
        else:
            self._status_lbl.setText(f"Ошибка: {err}")
            self._status_lbl.setStyleSheet("color: #ef4444;")
            self._btn_update.setEnabled(True)

    def _request_restart(self):
        self.restart_requested.emit()
        self.accept()

    def _open_release_page(self):
        if self._info.html_url:
            QDesktopServices.openUrl(QUrl(self._info.html_url))

    def closeEvent(self, event):
        if self._downloader:
            self._downloader.cancel()
        super().closeEvent(event)
