"""帳號頁：新增／重新登入／啟停用／刪除。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from qfluentwidgets import (
    CaptionLabel,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    PrimaryPushButton,
    SimpleCardWidget,
    SmoothScrollArea,
    StrongBodyLabel,
    SubtitleLabel,
)

from app.ui.components import AccountCard, make_background_transparent


class AccountPage(SmoothScrollArea):
    """管理多個 MiniMax 帳號（每個帳號一份獨立 session）。"""

    addRequested = Signal()
    reloginRequested = Signal(str)
    deleteRequested = Signal(str)
    enabledChanged = Signal(str, bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("accountPage")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        make_background_transparent(self)

        container = QWidget()
        container.setObjectName("accountContainer")
        make_background_transparent(container)
        self.setWidget(container)

        self.vBox = QVBoxLayout(container)
        self.vBox.setContentsMargins(28, 24, 28, 28)
        self.vBox.setSpacing(16)
        self._cards: dict[str, AccountCard] = {}

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_box.addWidget(SubtitleLabel("帳號管理", self))
        title_box.addWidget(
            CaptionLabel(
                "每個帳號使用獨立的瀏覽器 session（cookie 互相隔離），只需登入一次。", self
            )
        )
        header.addLayout(title_box)
        header.addStretch(1)
        self.addButton = PrimaryPushButton("新增帳號", self, FluentIcon.ADD)
        self.addButton.setFixedWidth(140)
        self.addButton.clicked.connect(self.addRequested)
        header.addWidget(self.addButton)
        self.vBox.addLayout(header)

        self.hintCard = SimpleCardWidget(self)
        self.hintCard.setFixedHeight(88)
        hint_layout = QVBoxLayout(self.hintCard)
        hint_layout.setContentsMargins(20, 12, 20, 12)
        hint_layout.setSpacing(2)
        hint_layout.addWidget(StrongBodyLabel("如何新增帳號？", self.hintCard))
        hint_layout.addWidget(
            CaptionLabel(
                "按「新增帳號」後會開啟瀏覽器視窗，請在該視窗完成登入"
                "（Google／Email 驗證碼／GitHub），登入成功後程式會自動儲存 session 並關閉視窗。",
                self.hintCard,
            )
        )
        self.vBox.addWidget(self.hintCard)

        self.listLayout = QVBoxLayout()
        self.listLayout.setSpacing(10)
        self.vBox.addLayout(self.listLayout)

        self.emptyLabel = CaptionLabel("目前沒有帳號。", self)
        self.vBox.addWidget(self.emptyLabel)
        self.vBox.addStretch(1)

    # ------------------------------------------------------------------
    def update_accounts(self, rows: list[dict]) -> None:
        self.emptyLabel.setVisible(not rows)
        seen = set()
        for row in rows:
            account_id = str(row.get("id", ""))
            seen.add(account_id)
            card = self._cards.get(account_id)
            if card is None:
                card = AccountCard(row, self)
                card.reloginRequested.connect(self.reloginRequested)
                card.deleteRequested.connect(self.deleteRequested)
                card.enabledChanged.connect(self.enabledChanged)
                self._cards[account_id] = card
                self.listLayout.addWidget(card)
            else:
                card.update_data(row)
        for account_id in list(self._cards):
            if account_id not in seen:
                card = self._cards.pop(account_id)
                self.listLayout.removeWidget(card)
                card.deleteLater()

    def set_busy(self, account_id: str, busy: bool) -> None:
        """標記某帳號是否正在進行登入（顯示轉圈圈、禁用按鈕）。"""
        card = self._cards.get(str(account_id))
        if card is not None:
            card.set_busy(bool(busy))

    def notify(self, title: str, content: str, success: bool = True) -> None:
        (InfoBar.success if success else InfoBar.warning)(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=4000,
            parent=self,
        )
