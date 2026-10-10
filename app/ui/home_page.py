"""總覽頁：今日狀態、統計、一鍵簽到、各帳號結果。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from qfluentwidgets import (
    CaptionLabel,
    FluentIcon,
    IndeterminateProgressBar,
    PrimaryPushButton,
    PushButton,
    SimpleCardWidget,
    SmoothScrollArea,
    StrongBodyLabel,
    SubtitleLabel,
)

from app.constants import APP_VERSION, SELECTOR_PACK_VERSION
from app.i18n import t
from app.ui.components import (
    COLOR_INFO,
    COLOR_MUTED,
    COLOR_WARN,
    ResultCard,
    StatCard,
    make_background_transparent,
    pill,
)

STATUS_KEYS = ("running", "ok", "partial", "fail", "idle")


class HomePage(SmoothScrollArea):
    """首頁：一鍵簽到與結果總覽。"""

    runRequested = Signal()
    cancelRequested = Signal()
    probeRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("homePage")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 讓內容區跟隨 qfluentwidgets 的主題背景（透明），
        # 否則 Qt 會用系統深色調色盤繪製，導致淺色主題下內容區仍是深色。
        make_background_transparent(self)

        container = QWidget()
        container.setObjectName("homeContainer")
        make_background_transparent(container)
        self.setWidget(container)

        self.vBox = QVBoxLayout(container)
        self.vBox.setContentsMargins(28, 24, 28, 28)
        self.vBox.setSpacing(16)
        self._result_cards: dict[str, ResultCard] = {}
        self._build_header()
        self._build_stats()
        self._build_warning()
        self._build_results()
        self.vBox.addStretch(1)

    # ------------------------------------------------------------------
    def _build_header(self) -> None:
        header = QHBoxLayout()
        header.setSpacing(12)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.titleLabel = SubtitleLabel(t("home.title"), self)
        self.subtitleLabel = CaptionLabel(
            t("home.subtitle", version=APP_VERSION, pack=SELECTOR_PACK_VERSION), self
        )
        title_box.addWidget(self.titleLabel)
        title_box.addWidget(self.subtitleLabel)
        header.addLayout(title_box)
        header.addStretch(1)

        self.statusPill = pill(t("home.status.idle"), COLOR_MUTED)
        header.addWidget(self.statusPill)

        self.runButton = PrimaryPushButton(t("nav.run_now"), self, FluentIcon.PLAY)
        self.runButton.setFixedWidth(140)
        self.cancelButton = PushButton(t("home.cancel"), self, FluentIcon.CANCEL)
        self.cancelButton.setEnabled(False)
        header.addWidget(self.runButton)
        header.addWidget(self.cancelButton)
        self.runButton.clicked.connect(self.runRequested)
        self.cancelButton.clicked.connect(self.cancelRequested)
        self.vBox.addLayout(header)

        self.progress = IndeterminateProgressBar(self)
        self.progress.setVisible(False)
        self.vBox.addWidget(self.progress)

    def _build_stats(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(16)
        self.todayCard = StatCard(t("home.stat.today"), "0 / 0", self)
        self.pointsCard = StatCard(t("home.stat.points"), "0", self)
        self.totalCard = StatCard(t("home.stat.total"), "0", self)
        self.nextCard = StatCard(t("home.stat.next"), "-", self)
        for card in (self.todayCard, self.pointsCard, self.totalCard, self.nextCard):
            row.addWidget(card, 1)
        self.vBox.addLayout(row)

    def _build_warning(self) -> None:
        self.warningCard = SimpleCardWidget(self)
        self.warningCard.setFixedHeight(84)
        layout = QHBoxLayout(self.warningCard)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(12)
        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        text_box.addWidget(StrongBodyLabel(t("home.drift.title"), self.warningCard))
        text_box.addWidget(
            CaptionLabel(
                t("home.drift.body"),
                self.warningCard,
            )
        )
        layout.addLayout(text_box)
        layout.addStretch(1)
        self.probeButton = PushButton(t("home.drift.rescan"), self.warningCard, FluentIcon.SEARCH)
        self.probeButton.clicked.connect(self.probeRequested)
        layout.addWidget(self.probeButton)
        self.warningCard.setVisible(False)
        self.vBox.addWidget(self.warningCard)

    def _build_results(self) -> None:
        self.resultsTitle = StrongBodyLabel(t("home.results.title"), self)
        self.vBox.addWidget(self.resultsTitle)
        self.resultsLayout = QVBoxLayout()
        self.resultsLayout.setSpacing(10)
        self.vBox.addLayout(self.resultsLayout)
        self.emptyLabel = CaptionLabel(t("home.results.empty"), self)
        self.vBox.addWidget(self.emptyLabel)

    # ------------------------------------------------------------------
    def update_summary(self, summary: dict, next_run_text: str, running: bool) -> None:
        total = int(summary.get("enabled", 0))
        done = int(summary.get("done_today", 0))
        self.todayCard.setValue(f"{done} / {total}")
        self.pointsCard.setValue(str(summary.get("points_today", 0)))
        self.totalCard.setValue(str(summary.get("points_total", 0)))
        self.nextCard.setValue(next_run_text or "-")
        if total == 0:
            key = "idle"
        elif done >= total:
            key = "ok"
        else:
            key = "partial" if done else "fail"
        self.set_status(key)
        self.set_running(running)

    def set_status(self, key: str) -> None:
        rgb = {
            "running": COLOR_INFO,
            "ok": (34, 197, 94),
            "partial": COLOR_WARN,
            "fail": (239, 68, 68),
            "idle": COLOR_MUTED,
        }.get(key, COLOR_MUTED)
        key = key if key in STATUS_KEYS else "idle"
        self.statusPill.setText(t(f"home.status.{key}"))
        self.statusPill.setStyleSheet(
            "QLabel{"
            f"color: rgb({rgb[0]},{rgb[1]},{rgb[2]});"
            f"background: rgba({rgb[0]},{rgb[1]},{rgb[2]},0.16);"
            "border-radius: 9px; padding: 3px 12px; font-size: 12px;}"
        )

    def set_running(self, running: bool) -> None:
        self.runButton.setEnabled(not running)
        self.cancelButton.setEnabled(running)
        self.progress.setVisible(running)
        if running:
            self.set_status("running")

    def set_drift_warning(self, enabled: bool) -> None:
        self.warningCard.setVisible(bool(enabled))

    def update_results(self, rows: list[dict]) -> None:
        """以最新的帳號結果重建清單。"""
        self.emptyLabel.setVisible(not rows)
        seen = set()
        for row in rows:
            account_id = str(row.get("account_id", ""))
            seen.add(account_id)
            card = self._result_cards.get(account_id)
            if card is None:
                card = ResultCard(row, self)
                self._result_cards[account_id] = card
                self.resultsLayout.addWidget(card)
            else:
                card.update_data(row)
        for account_id in list(self._result_cards):
            if account_id not in seen:
                card = self._result_cards.pop(account_id)
                self.resultsLayout.removeWidget(card)
                card.deleteLater()