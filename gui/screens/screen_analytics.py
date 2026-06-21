"""
Экран 6: Аналитика.
Открытия (tracking pixel), клики, bounces, экспорт CSV/PDF.
"""
import csv
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List

logger = logging.getLogger("analytics")

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QFileDialog, QMessageBox, QTabWidget, QComboBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor

from core.sender import SendResult
from gui.theme import Colors, Spacing

# FIX: use absolute APPDATA path — relative path fails when app is launched from shortcut/different CWD
ANALYTICS_FILE = Path(os.environ.get("APPDATA", ".")) / "FMailSender" / "analytics.json"


def _load_analytics() -> dict:
    if ANALYTICS_FILE.exists():
        try:
            with open(ANALYTICS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Ошибка загрузки аналитики: {e}")
    return {"campaigns": [], "opens": {}, "clicks": {}, "bounces": []}


def _save_analytics(data: dict) -> None:
    ANALYTICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ANALYTICS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class AnalyticsSummaryCard(QFrame):
    def __init__(self, title: str, value: str, subtitle: str = "", color: str = Colors.TEXT_PRIMARY, parent=None):
        super().__init__(parent)
        self.setObjectName("kpi_card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(4)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {color};")
        layout.addWidget(self.value_label)

        title_lbl = QLabel(title.upper())
        title_lbl.setObjectName("label_kpi_title")
        layout.addWidget(title_lbl)

        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setObjectName("label_muted")
            layout.addWidget(sub_lbl)

    def set_value(self, v: str):
        self.value_label.setText(v)


class AnalyticsScreen(QWidget):
    """Экран аналитики рассылок."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = _load_analytics()
        self._current_results: List[SendResult] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.LG)

        # ── Заголовок ────────────────────────────
        header_row = QHBoxLayout()
        title = QLabel("Аналитика")
        title.setObjectName("section_header")
        header_row.addWidget(title)
        header_row.addStretch()

        self.campaign_combo = QComboBox()
        self.campaign_combo.setMinimumWidth(220)
        self.campaign_combo.setToolTip("История кампаний")
        self.campaign_combo.addItem("Текущая кампания")
        self.campaign_combo.currentIndexChanged.connect(self._load_campaign)
        header_row.addWidget(self.campaign_combo)

        refresh_btn = QPushButton("Обновить")
        refresh_btn.setObjectName("btn_secondary")
        refresh_btn.clicked.connect(self._refresh)
        header_row.addWidget(refresh_btn)

        layout.addLayout(header_row)

        # ── Сводные карточки ─────────────────────
        summary_row = QHBoxLayout()
        summary_row.setSpacing(Spacing.MD)

        self.card_sent = AnalyticsSummaryCard("Отправлено", "0")
        self.card_delivered = AnalyticsSummaryCard("Доставлено", "0%", color=Colors.SUCCESS)
        self.card_opens = AnalyticsSummaryCard("Открытий", "0%", color=Colors.INFO)
        self.card_clicks = AnalyticsSummaryCard("Кликов", "0%", color=Colors.ACCENT)
        for card in [self.card_sent, self.card_delivered, self.card_opens,
                     self.card_clicks]:
            card.setFixedHeight(100)
            summary_row.addWidget(card)

        layout.addLayout(summary_row)

        # ── Вкладки детальной аналитики ──────────
        tabs = QTabWidget()

        # Вкладка: детали отправки
        send_tab = QWidget()
        send_layout = QVBoxLayout(send_tab)
        self.results_table = self._build_results_table()
        send_layout.addWidget(self.results_table)
        tabs.addTab(send_tab, "Результаты отправки")

        # Вкладка: bounces
        bounce_tab = QWidget()
        bounce_layout = QVBoxLayout(bounce_tab)
        self.bounce_table = self._build_bounce_table()
        bounce_layout.addWidget(self.bounce_table)
        tabs.addTab(bounce_tab, "Отказы (Bounces)")

        # Вкладка: SPF/DKIM/DMARC
        dns_tab = QWidget()
        dns_layout = QVBoxLayout(dns_tab)
        dns_layout.setSpacing(Spacing.LG)

        dns_info = QLabel(
            "Проверка DNS-аутентификации домена отправителя.\n"
            "Правильно настроенные SPF, DKIM и DMARC значительно улучшают доставляемость."
        )
        dns_info.setObjectName("label_muted")
        dns_info.setWordWrap(True)
        dns_layout.addWidget(dns_info)

        dns_input_row = QHBoxLayout()
        from PyQt6.QtWidgets import QLineEdit
        self.dns_domain_input = QLineEdit()
        self.dns_domain_input.setPlaceholderText("example.com")
        dns_input_row.addWidget(self.dns_domain_input)
        check_dns_btn = QPushButton("Проверить DNS")
        check_dns_btn.setObjectName("btn_primary")
        check_dns_btn.clicked.connect(self._check_dns)
        dns_input_row.addWidget(check_dns_btn)
        dns_layout.addLayout(dns_input_row)

        self.dns_result_label = QLabel("")
        self.dns_result_label.setWordWrap(True)
        dns_layout.addWidget(self.dns_result_label)
        dns_layout.addStretch()
        tabs.addTab(dns_tab, "SPF / DKIM / DMARC")

        layout.addWidget(tabs, 1)

        # ── Экспорт ───────────────────────────────
        export_row = QHBoxLayout()
        export_row.addStretch()

        export_csv_btn = QPushButton("Экспорт CSV")
        export_csv_btn.clicked.connect(self._export_csv)
        export_row.addWidget(export_csv_btn)

        export_pdf_btn = QPushButton("Экспорт PDF")
        export_pdf_btn.clicked.connect(self._export_pdf)
        export_row.addWidget(export_pdf_btn)

        layout.addLayout(export_row)

    def _build_results_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Email", "Статус", "Аккаунт", "Message-ID", "Время"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        return table

    def _build_bounce_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Email", "Тип", "Код", "Сообщение", "Дата"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        return table

    def on_results(self, results: list) -> None:
        """Слот для сигнала campaign_finished из SendingScreen."""
        self.update_results(results)

    def update_results(self, results: List[SendResult]) -> None:
        """Обновляет данные после завершения кампании."""
        self._current_results = results
        self._refresh_results_table()
        self._refresh_summary()
        self._save_campaign(results)
        self._refresh_campaign_combo()

    def _refresh_results_table(self):
        results = self._current_results
        self.results_table.setRowCount(len(results))
        for row, r in enumerate(results):
            self.results_table.setItem(row, 0, QTableWidgetItem(r.recipient_email))

            status_item = QTableWidgetItem("Успешно" if r.success else f"{r.error[:40]}")
            status_item.setForeground(
                QColor(Colors.SUCCESS) if r.success else QColor(Colors.ERROR)
            )
            self.results_table.setItem(row, 1, status_item)
            self.results_table.setItem(row, 2, QTableWidgetItem(r.account_used))
            self.results_table.setItem(row, 3, QTableWidgetItem(r.message_id[:40] if r.message_id else ""))

            ts = datetime.fromtimestamp(r.timestamp).strftime("%H:%M:%S")
            self.results_table.setItem(row, 4, QTableWidgetItem(ts))
            self.results_table.setRowHeight(row, 38)

    def _refresh_summary(self):
        results = self._current_results
        total = len(results)
        success = sum(1 for r in results if r.success)

        self.card_sent.set_value(str(total) if total > 0 else "0")
        pct_delivered = f"{int(success/total*100)}%" if total > 0 else "—"
        self.card_delivered.set_value(pct_delivered)

        # Opens и clicks требуют внешний tracking-pixel сервер — N/A
        self.card_opens.set_value("N/A")
        self.card_opens.setToolTip("Требуется tracking-pixel сервер. Открытия не отслеживаются.")
        self.card_clicks.set_value("N/A")
        self.card_clicks.setToolTip("Требуется перезапись ссылок. Клики не отслеживаются.")


    def _save_campaign(self, results: List[SendResult]) -> None:
        campaign = {
            "id": datetime.now().isoformat(),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total": len(results),
            "success": sum(1 for r in results if r.success),
            "errors": sum(1 for r in results if not r.success),
            "results": [
                {"email": r.recipient_email, "success": r.success, "error": r.error}
                for r in results
            ],
        }
        self._data["campaigns"].append(campaign)
        _save_analytics(self._data)



    def _load_campaign(self, index: int):
        if index == 0:
            self._refresh_results_table()
        else:
            campaigns = self._data.get("campaigns", [])
            idx = len(campaigns) - index
            if 0 <= idx < len(campaigns):
                camp = campaigns[idx]
                fake_results = [
                    SendResult(
                        recipient_email=r["email"],
                        success=r["success"],
                        error=r.get("error", ""),
                    )
                    for r in camp.get("results", [])
                ]
                self._current_results = fake_results
                self._refresh_results_table()
                self._refresh_summary()

    def _refresh(self):
        self._data = _load_analytics()
        self._refresh_campaign_combo()
        self._refresh_results_table()
        self._refresh_summary()
        self._refresh_bounce_table()

    def _refresh_campaign_combo(self) -> None:
        """Обновляет список кампаний в выпадающем меню."""
        self.campaign_combo.blockSignals(True)
        current = self.campaign_combo.currentIndex()
        self.campaign_combo.clear()
        self.campaign_combo.addItem("Текущая кампания")
        campaigns = self._data.get("campaigns", [])
        for camp in reversed(campaigns):
            label = f"{camp.get('date', '—')}  ({camp.get('success', 0)}/{camp.get('total', 0)})"
            self.campaign_combo.addItem(label)
        idx = min(current, self.campaign_combo.count() - 1)
        self.campaign_combo.setCurrentIndex(idx)
        self.campaign_combo.blockSignals(False)

    def _refresh_bounce_table(self):
        bounces = self._data.get("bounces", [])
        self.bounce_table.setRowCount(len(bounces))
        for row, b in enumerate(bounces):
            self.bounce_table.setItem(row, 0, QTableWidgetItem(b.get("email", "")))
            bt = b.get("bounce_type", "unknown")
            bt_item = QTableWidgetItem(bt.upper())
            bt_item.setForeground(QColor(Colors.ERROR if bt == "hard" else Colors.WARNING))
            self.bounce_table.setItem(row, 1, bt_item)
            self.bounce_table.setItem(row, 2, QTableWidgetItem(b.get("code", "")))
            self.bounce_table.setItem(row, 3, QTableWidgetItem(b.get("message", "")[:60]))
            self.bounce_table.setItem(row, 4, QTableWidgetItem(b.get("received_at", "")[:19]))
            self.bounce_table.setRowHeight(row, 38)

    def _check_dns(self):
        domain = self.dns_domain_input.text().strip()
        if not domain:
            return
        try:
            from core.spam_checker import check_dns_auth
            status = check_dns_auth(domain)

            lines = [f"<b>Домен: {domain}</b><br>"]
            if status.spf_valid:
                spf_val = "<span style='color:#10B981'>Настроен</span>" + (f" {status.spf[:80]}" if status.spf else "")
            else:
                spf_val = "<span style='color:#EF4444'>Не настроен</span>"
            lines.append(f"SPF: {spf_val}<br>")
            dkim_val = "<span style='color:#10B981'>Настроен</span>" if status.dkim_valid else "<span style='color:#EF4444'>Не найден</span>"
            lines.append(f"DKIM: {dkim_val}<br>")
            if status.dmarc_valid:
                dmarc_val = "<span style='color:#10B981'>Настроен</span>" + (f" {status.dmarc[:80]}" if status.dmarc else "")
            else:
                dmarc_val = "<span style='color:#EF4444'>Не настроен</span>"
            lines.append(f"DMARC: {dmarc_val}<br>")

            if status.suggestions:
                lines.append("<br><b>Рекомендации:</b><br>")
                for s in status.suggestions:
                    lines.append(f"• {s[:150]}<br>")

            self.dns_result_label.setText("".join(lines))
        except Exception as e:
            self.dns_result_label.setText(f"Ошибка проверки DNS: {e}")

    def _export_csv(self):
        if not self._current_results:
            QMessageBox.information(self, "Нет данных", "Нет данных для экспорта")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт в CSV", f"report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "CSV files (*.csv)"
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Email", "Статус", "Аккаунт", "Message-ID", "Ошибка", "Время"])
            for r in self._current_results:
                writer.writerow([
                    r.recipient_email,
                    "Успешно" if r.success else "Ошибка",
                    r.account_used,
                    r.message_id,
                    r.error,
                    datetime.fromtimestamp(r.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                ])
        QMessageBox.information(self, "Экспорт", f"Сохранено: {path}")

    def _export_pdf(self):
        if not self._current_results:
            QMessageBox.information(self, "Нет данных", "Нет данных для экспорта")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт в PDF", f"report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            "PDF files (*.pdf)"
        )
        if not path:
            return
        try:
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import cm

            doc = SimpleDocTemplate(path, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []

            story.append(Paragraph("Отчёт Email Sender Pro", styles["Title"]))
            story.append(Paragraph(
                f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')} | "
                f"Отправлено: {len(self._current_results)}",
                styles["Normal"]
            ))
            story.append(Spacer(1, 0.5*cm))

            total = len(self._current_results)
            success = sum(1 for r in self._current_results if r.success)
            error = total - success

            summary_data = [
                ["Показатель", "Значение"],
                ["Всего отправлено", str(total)],
                ["Успешно", str(success)],
                ["Ошибок", str(error)],
                ["Процент доставки", f"{int(success/total*100)}%" if total else "0%"],
            ]
            t = Table(summary_data, colWidths=[8*cm, 8*cm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6366F1")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F5F5F5"), colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]))
            story.append(t)
            story.append(Spacer(1, 0.5*cm))

            # Детали (первые 100)
            story.append(Paragraph("Детали отправки (первые 100 записей):", styles["Heading2"]))
            detail_data = [["Email", "Статус", "Аккаунт"]]
            for r in self._current_results[:100]:
                detail_data.append([
                    r.recipient_email[:40],
                    "Успешно" if r.success else f"Ошибка: {r.error[:30]}",
                    r.account_used[:30],
                ])
            dt = Table(detail_data, colWidths=[7*cm, 5*cm, 5*cm])
            dt.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#374151")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("PADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F9FAFB"), colors.white]),
            ]))
            story.append(dt)

            doc.build(story)
            QMessageBox.information(self, "Экспорт", f"PDF сохранён: {path}")

        except ImportError:
            QMessageBox.warning(self, "Ошибка", "Установите reportlab: pip install reportlab")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка PDF", str(e))
