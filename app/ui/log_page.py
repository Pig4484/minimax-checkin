"""紀錄頁：即時日誌檢視與匯出。"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget

from qfluentwidgets import (
    CaptionLabel,
    ComboBox,
    FluentIcon,
    PushButton,
    SmoothScrollArea,
    SubtitleLabel,
    SwitchButton,
)

from app import paths
from app.i18n import t
from app.ui.components import make_background_transparent

MAX_LINES = 5000


class LogPage(QWidget):
    """顯示 loguru 的即時輸出，並可匯出成檔案。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("logPage")
        self._lines: list[str] = []
        self._level = "DEBUG"
        make_background_transparent(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_box.addWidget(SubtitleLabel(t("logs.title"), self))
        title_box.addWidget(CaptionLabel(t("logs.subtitle"), self))
        header.addLayout(title_box)
        header.addStretch(1)

        self.levelCombo = ComboBox(self)
        self.levelCombo.addItems([t("logs.level.all"), t("logs.level.info"), t("logs.level.warn"), t("logs.level.error")])
        self.levelCombo.setCurrentIndex(1)
        self.levelCombo.setFixedWidth(130)
        self.levelCombo.currentIndexChanged.connect(self._on_level_changed)
        header.addWidget(self.levelCombo)

        self.autoScroll = SwitchButton(self)
        self.autoScroll.setOnText(t("logs.autoscroll"))
        self.autoScroll.setOffText(t("logs.autoscroll"))
        self.autoScroll.setChecked(True)
        header.addWidget(self.autoScroll)

        self.clearButton = PushButton(t("logs.clear"), self, FluentIcon.BROOM)
        self.clearButton.clicked.connect(self.clear)
        header.addWidget(self.clearButton)

        self.folderButton = PushButton(t("logs.open_folder"), self, FluentIcon.FOLDER)
        self.folderButton.clicked.connect(self._open_logs_folder)
        header.addWidget(self.folderButton)

        self.exportButton = PushButton(t("logs.export"), self, FluentIcon.SAVE)
        self.exportButton.clicked.connect(self._export)
        header.addWidget(self.exportButton)
        layout.addLayout(header)

        self.view = QPlainTextEdit(self)
        self.view.setReadOnly(True)
        self.view.setObjectName("logView")
        font = QFont("Cascadia Mono")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(9)
        self.view.setFont(font)
        self.view.setLineWrapMode(QPlainTextEdit.NoWrap)
        layout.addWidget(self.view, 1)

    # ------------------------------------------------------------------
    def _on_level_changed(self, index: int) -> None:
        self._level = {0: "DEBUG", 1: "INFO", 2: "WARNING", 3: "ERROR"}.get(index, "DEBUG")
        self._render()

    def append(self, level: str, line: str) -> None:
        self._lines.append(f"{level} {line}")
        if len(self._lines) > MAX_LINES:
            self._lines = self._lines[-MAX_LINES:]
            self._render()
            return
        if self._passes(level):
            self.view.appendPlainText(line)
            if self.autoScroll.isChecked():
                self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())

    def _passes(self, level: str) -> bool:
        order = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "SUCCESS": 1, "CRITICAL": 3}
        threshold = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}.get(self._level, 0)
        return order.get(level.upper(), 1) >= threshold

    def _render(self) -> None:
        rows = [line for line in self._lines if self._passes(line.split(" ", 1)[0])]
        self.view.setPlainText("\n".join(rows))
        if self.autoScroll.isChecked():
            self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())

    def clear(self) -> None:
        self._lines.clear()
        self.view.clear()

    def _open_logs_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.logs_dir())))

    def _export(self) -> None:
        default = f"minimax-checkin-log-{datetime.now():%Y%m%d_%H%M%S}.txt"
        path, _ = QFileDialog.getSaveFileName(self, t("logs.export.title"), default, t("logs.export.filter"))
        if not path:
            return
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self.view.toPlainText())
