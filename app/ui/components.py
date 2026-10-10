"""自訂 Fluent 卡片元件（設定卡片風格比照 Ghost Downloader）。"""

from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    IndeterminateProgressRing,
    LineEdit,
    SettingCard,
    SimpleCardWidget,
    SpinBox,
    StrongBodyLabel,
    SwitchButton,
    ToolButton,
)

from app.i18n import t

# 狀態顏色（RGB）——深色主題下也清楚可辨
COLOR_SUCCESS = (34, 197, 94)
COLOR_FAIL = (239, 68, 68)
COLOR_WARN = (245, 158, 11)
COLOR_INFO = (59, 130, 246)
COLOR_MUTED = (148, 163, 184)

STATUS_COLORS = {
    "success": COLOR_SUCCESS,
    "already": COLOR_SUCCESS,
    "failed": COLOR_FAIL,
    "need_relogin": COLOR_WARN,
    "rate_limited": COLOR_WARN,
    "drift": COLOR_WARN,
    "running": COLOR_INFO,
    "idle": COLOR_MUTED,
}


def _flat_label(label: "QLabel") -> "QLabel":
    """讓卡片內的文字標籤不繪製自身背景（避免在半透明卡片上顯出方框）。

    Fluent 的 CaptionLabel / StrongBodyLabel 等自帶主題 qss，在
    ElevatedCardWidget（半透明）內會讓文字框底色與卡片不一致，
    看起來就是一塊塊深淺不同的方框。這裡強制關閉自動填充並清理
    可能殘留的背景屬性，只保留文字顏色。
    """
    try:
        label.setAutoFillBackground(False)
    except Exception:
        pass
    try:
        from PySide6.QtCore import Qt

        label.setAttribute(Qt.WA_OpaquePaintEvent, False)
        label.setAttribute(Qt.WA_NoSystemBackground, True)
    except Exception:
        pass
    return label


# 內容區底色（Qt 調色盤）：診斷證實 SmoothScrollArea 的 viewport 會忽略
# Fluent QSS，真正底色是內容容器 QWidget 的 Window 色彩角色。
# 淺色 #f9f9f9（視窗）/#ffffff（卡片區）、深色 #202020/#282828（對齊 FluentWidget 官方底色）。
PAGE_PALETTES = {
    True: {"window": "#202020", "base": "#282828", "text": "#f3f3f3"},
    False: {"window": "#f9f9f9", "base": "#ffffff", "text": "#1b1b1b"},
}


def sync_page_palettes(window) -> None:
    """把各頁面容器／viewport 的調色盤同步為目前主題（修正深淺不一致）。"""
    try:
        from PySide6.QtGui import QColor, QPalette

        from qfluentwidgets import isDarkTheme

        pal = PAGE_PALETTES[bool(isDarkTheme())]
        bg = QColor(pal["window"])
        base = QColor(pal["base"])
        text = QColor(pal["text"])
        pages = [getattr(window, n, None) for n in ("homePage", "accountPage", "logPage", "settingsPage")]
        for page in pages:
            if page is None:
                continue
            targets = [page]
            try:
                widget = page.widget()
                if widget is not None:
                    targets.append(widget)
            except Exception:
                pass
            try:
                viewport = page.viewport()
                if viewport is not None:
                    targets.append(viewport)
            except Exception:
                pass
            for target in targets:
                try:
                    p = target.palette()
                    p.setColor(QPalette.ColorRole.Window, bg)
                    p.setColor(QPalette.ColorRole.Base, base)
                    p.setColor(QPalette.ColorRole.WindowText, text)
                    p.setColor(QPalette.ColorRole.Text, text)
                    target.setPalette(p)
                    if target is not page or target.autoFillBackground():
                        target.setAutoFillBackground(True)
                    target.update()
                except Exception:
                    continue
    except Exception:
        pass


def plain_caption(text: str, parent=None) -> "QLabel":
    """卡片／Header 內的說明文字：使用原生 QLabel，避免 Fluent Label 帶底。"""
    label = QLabel(text, parent)
    _flat_label(label)
    return label


def sync_qt_color_scheme() -> None:
    """讓 Qt 的 colorScheme 跟隨 App 主題（而非 Windows 系統設定）。

    Qt 6.8+ 的 `QStyleHints.colorScheme()` 預設跟隨系統；當 App 選擇「淺色」但
    系統是深色時，使用原生調色盤繪製的元件會變成深色而與主題不符。
    """
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication

        from qfluentwidgets import isDarkTheme

        app = QApplication.instance()
        if app is None:
            return
        hints = app.styleHints()
        if not hasattr(hints, "setColorScheme"):
            return
        hints.setColorScheme(Qt.ColorScheme.Dark if isDarkTheme() else Qt.ColorScheme.Light)
    except Exception:
        pass


def page_background_color() -> "QColor":
    """(Deprecated) kept only for old unit tests; Fluent native theme owns backgrounds."""
    from PySide6.QtGui import QColor
    from qfluentwidgets import isDarkTheme

    return QColor("#202020") if isDarkTheme() else QColor("#f9f9f9")


def make_background_transparent(widget) -> None:
    """(Deprecated) no-op cleaner; Fluent native QSS owns page backgrounds."""
    try:
        if widget.styleSheet() and "background" in widget.styleSheet().lower():
            widget.setStyleSheet("")
    except Exception:
        pass
    try:
        viewport = widget.viewport()
        if viewport is not None and viewport.styleSheet() and "background" in viewport.styleSheet().lower():
            viewport.setStyleSheet("")
    except Exception:
        pass


def refresh_page_backgrounds(window) -> None:
    """(Deprecated) no-op; backgrounds belong to Fluent native mechanism."""
    try:
        stacked = window.stackedWidget
    except Exception:
        return
    try:
        if stacked.styleSheet() and "background" in stacked.styleSheet().lower():
            stacked.setStyleSheet("")
            stacked.update()
    except Exception:
        pass



def pill(text: str, rgb: tuple[int, int, int]) -> QLabel:
    """狀態膠囊標籤。"""
    label = QLabel(text)
    label.setStyleSheet(
        "QLabel{"
        f"color: rgb({rgb[0]},{rgb[1]},{rgb[2]});"
        f"background: rgba({rgb[0]},{rgb[1]},{rgb[2]},0.16);"
        "border-radius: 9px; padding: 2px 10px; font-size: 12px;}"
    )
    label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    return label


def avatar_pixmap(name: str, size: int = 40) -> QPixmap:
    """以名稱首字產生圓角頭像（不需下載圖片）。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, QColor("#3b82f6"))
    gradient.setColorAt(1.0, QColor("#7c3aed"))
    path = QPainterPath()
    path.addRoundedRect(1, 1, size - 2, size - 2, size * 0.32, size * 0.32)
    painter.fillPath(path, gradient)
    painter.setPen(QColor(255, 255, 255))
    font = painter.font()
    font.setPointSizeF(size * 0.42)
    font.setBold(True)
    painter.setFont(font)
    initial = (name or "?").strip()[:1].upper()
    painter.drawText(pixmap.rect(), Qt.AlignCenter, initial)
    painter.end()
    return pixmap


class SwitchCard(SettingCard):
    """開關設定卡片。"""

    checkedChanged = Signal(bool)

    def __init__(self, icon, title: str, content: str = "", parent=None) -> None:
        super().__init__(icon, title, content, parent)
        self.switch = SwitchButton(self)
        self.switch.setOnText("On")
        self.switch.setOffText("Off")
        self.hBoxLayout.addWidget(self.switch, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.switch.checkedChanged.connect(self.checkedChanged)

    def value(self) -> bool:
        return self.switch.isChecked()

    def setValue(self, value: bool) -> None:
        self.switch.setChecked(bool(value))


class ComboCard(SettingCard):
    """下拉選單設定卡片。"""

    valueChanged = Signal(str)

    def __init__(self, icon, title: str, options: Iterable[tuple[str, str]],
                 content: str = "", parent=None) -> None:
        super().__init__(icon, title, content, parent)
        self.combo = ComboBox(self)
        for label, value in options:
            self.combo.addItem(label)
            self.combo.setItemData(self.combo.count() - 1, value)
        self.combo.setMinimumWidth(200)
        self.hBoxLayout.addWidget(self.combo, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.combo.currentIndexChanged.connect(lambda _: self.valueChanged.emit(self.value()))

    def value(self) -> str:
        return self.combo.currentData()

    def setValue(self, value: str) -> None:
        index = self.combo.findData(value)
        if index >= 0:
            self.combo.setCurrentIndex(index)


class SpinCard(SettingCard):
    """數值設定卡片。"""

    valueChanged = Signal(int)

    def __init__(self, icon, title: str, content: str = "", minimum: int = 0,
                 maximum: int = 100, suffix: str = "", parent=None) -> None:
        super().__init__(icon, title, content, parent)
        self.spin = SpinBox(self)
        self.spin.setRange(minimum, maximum)
        if suffix:
            self.spin.setSuffix(f" {suffix}")
        self.spin.setMinimumWidth(140)
        self.hBoxLayout.addWidget(self.spin, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.spin.valueChanged.connect(self.valueChanged)

    def value(self) -> int:
        return int(self.spin.value())

    def setValue(self, value: int) -> None:
        self.spin.setValue(int(value))


class TextCard(SettingCard):
    """文字輸入設定卡片。"""

    textChanged = Signal(str)

    def __init__(self, icon, title: str, content: str = "", placeholder: str = "",
                 width: int = 260, parent=None) -> None:
        super().__init__(icon, title, content, parent)
        self.edit = LineEdit(self)
        self.edit.setPlaceholderText(placeholder)
        self.edit.setClearButtonEnabled(True)
        self.edit.setFixedWidth(width)
        self.hBoxLayout.addWidget(self.edit, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.edit.textChanged.connect(self.textChanged)

    def value(self) -> str:
        return self.edit.text().strip()

    def setValue(self, value: str) -> None:
        self.edit.setText(value or "")


class AccountCard(SimpleCardWidget):
    """帳號列：頭像、名稱、狀態、啟用開關、重新登入、刪除。"""

    reloginRequested = Signal(str)
    renameRequested = Signal(str)
    deleteRequested = Signal(str)
    enabledChanged = Signal(str, bool)

    def __init__(self, data: dict, parent=None) -> None:
        super().__init__(parent)
        from qfluentwidgets import FluentIcon, PushButton, ToolButton, TransparentToolButton

        self.account_id = str(data.get("id", ""))
        self.setFixedHeight(84)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        self.avatarLabel = QLabel(self)
        self.avatarLabel.setFixedSize(44, 44)
        layout.addWidget(self.avatarLabel)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        self.nameLabel = StrongBodyLabel(str(data.get("name", "")), self)
        self.subLabel = CaptionLabel(str(data.get("sub", "")), self)
        text_box.addWidget(self.nameLabel)
        text_box.addWidget(self.subLabel)
        layout.addLayout(text_box)

        self.statusPill = pill(t("accounts.card.todo"), COLOR_MUTED)
        layout.addWidget(self.statusPill)
        layout.addStretch(1)

        self.messageLabel = CaptionLabel("", self)
        self.messageLabel.setWordWrap(False)
        layout.addWidget(self.messageLabel)

        self.enableSwitch = SwitchButton(self)
        self.enableSwitch.setOnText(t("accounts.card.on"))
        self.enableSwitch.setOffText(t("accounts.card.off"))
        layout.addWidget(self.enableSwitch)

        self.reloginButton = PushButton(t("accounts.card.relogin"), self, FluentIcon.SYNC)
        layout.addWidget(self.reloginButton)

        self.renameButton = ToolButton(FluentIcon.EDIT, self)
        self.renameButton.setToolTip(t("accounts.card.rename"))
        layout.addWidget(self.renameButton)

        self.deleteButton = TransparentToolButton(FluentIcon.DELETE, self)
        layout.addWidget(self.deleteButton)

        # 登入中的轉圈圈（預設隱藏）
        self.busyIndicator = IndeterminateProgressRing(self)
        self.busyIndicator.setFixedSize(18, 18)
        self.busyIndicator.setStrokeWidth(3)
        self.busyIndicator.setVisible(False)
        layout.addWidget(self.busyIndicator)

        self.enableSwitch.checkedChanged.connect(
            lambda checked: self.enabledChanged.emit(self.account_id, bool(checked))
        )
        self.reloginButton.clicked.connect(lambda: self.reloginRequested.emit(self.account_id))
        self.renameButton.clicked.connect(lambda: self.renameRequested.emit(self.account_id))
        self.deleteButton.clicked.connect(lambda: self.deleteRequested.emit(self.account_id))
        self.update_data(data)

    def update_data(self, data: dict) -> None:
        name = str(data.get("name", ""))
        self.nameLabel.setText(name)
        self.subLabel.setText(str(data.get("sub", "")))
        self.avatarLabel.setPixmap(avatar_pixmap(name, 44))
        status = str(data.get("status", "")) or "idle"
        self.statusPill.setText(str(data.get("status_text", t("accounts.card.todo"))))
        rgb = STATUS_COLORS.get(status, COLOR_MUTED)
        self.statusPill.setStyleSheet(
            "QLabel{"
            f"color: rgb({rgb[0]},{rgb[1]},{rgb[2]});"
            f"background: rgba({rgb[0]},{rgb[1]},{rgb[2]},0.16);"
            "border-radius: 9px; padding: 2px 10px; font-size: 12px;}"
        )
        message = str(data.get("message", ""))
        if len(message) > 40:
            message = message[:40] + "…"
        self.messageLabel.setText(message)
        self.enableSwitch.setChecked(bool(data.get("enabled", True)))

    def set_busy(self, busy: bool) -> None:
        """登入進行中：顯示轉圈圈並暫時禁用按鈕，避免重複觸發。"""
        self.busyIndicator.setVisible(bool(busy))
        self.reloginButton.setEnabled(not busy)
        self.renameButton.setEnabled(not busy)
        self.enableSwitch.setEnabled(not busy)
        self.deleteButton.setEnabled(not busy)
        if busy:
            self.reloginButton.setText(t("accounts.card.logging_in"))
            self.statusPill.setText(t("accounts.card.opening"))
            rgb = COLOR_INFO
            self.statusPill.setStyleSheet(
                "QLabel{"
                f"color: rgb({rgb[0]},{rgb[1]},{rgb[2]});"
                f"background: rgba({rgb[0]},{rgb[1]},{rgb[2]},0.16);"
                "border-radius: 9px; padding: 2px 10px; font-size: 12px;}"
            )
        else:
            self.reloginButton.setText(t("accounts.card.relogin"))


class ResultCard(SimpleCardWidget):
    """首頁的單一帳號執行結果列。"""

    def __init__(self, data: dict, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(72)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(14)

        self.avatarLabel = QLabel(self)
        self.avatarLabel.setFixedSize(36, 36)
        layout.addWidget(self.avatarLabel)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        self.nameLabel = BodyLabel("", self)
        self.timeLabel = CaptionLabel("", self)
        text_box.addWidget(self.nameLabel)
        text_box.addWidget(self.timeLabel)
        layout.addLayout(text_box)

        self.statusPill = pill("", COLOR_MUTED)
        layout.addWidget(self.statusPill)
        layout.addStretch(1)

        self.pointsLabel = StrongBodyLabel("", self)
        layout.addWidget(self.pointsLabel)
        self.update_data(data)

    def update_data(self, data: dict) -> None:
        name = str(data.get("alias", ""))
        self.nameLabel.setText(name)
        self.avatarLabel.setPixmap(avatar_pixmap(name, 36))
        self.timeLabel.setText(str(data.get("time", "")) or t("result.not_run"))
        status = str(data.get("status", "idle"))
        rgb = STATUS_COLORS.get(status, COLOR_MUTED)
        self.statusPill.setText(str(data.get("status_text", "")))
        self.statusPill.setStyleSheet(
            "QLabel{"
            f"color: rgb({rgb[0]},{rgb[1]},{rgb[2]});"
            f"background: rgba({rgb[0]},{rgb[1]},{rgb[2]},0.16);"
            "border-radius: 9px; padding: 2px 10px; font-size: 12px;}"
        )
        points = int(data.get("points") or 0)
        self.pointsLabel.setText(t("result.points", points=points) if points else "")
        self.setToolTip(str(data.get("message", "")))


class StatCard(SimpleCardWidget):
    """統計小卡（標題 + 大數字）。"""

    def __init__(self, title: str, value: str = "-", parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(96)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(4)
        self.titleLabel = CaptionLabel(title, self)
        self.valueLabel = StrongBodyLabel(value, self)
        layout.addWidget(self.titleLabel)
        layout.addWidget(self.valueLabel)
        layout.addStretch(1)

    def setValue(self, value: str) -> None:
        self.valueLabel.setText(value)
