"""設定頁：所有可調設定（卡片式，仿 Ghost Downloader）。"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QHBoxLayout, QWidget

from qfluentwidgets import (
    CaptionLabel,
    FluentIcon,
    MessageBoxBase,
    PushSettingCard,
    SettingCard,
    SettingCardGroup,
    SmoothScrollArea,
    SpinBox,
    SubtitleLabel,
)

from app import paths
from app.config import (
    BROWSER_CHOICES,
    BROWSER_LABELS,
    LOG_LEVELS,
    THEME_DARK,
    THEME_LIGHT,
    THEME_SYSTEM,
)
from app.constants import APP_NAME, APP_NAME_CN, APP_VERSION, SELECTOR_PACK_VERSION
from app.ui.components import ComboCard, SpinCard, SwitchCard, TextCard, make_background_transparent


def browser_status_text() -> str:
    """瀏覽器核心狀態說明（給設定卡片顯示）。"""
    from app.core.browser import browser_status

    status = browser_status()
    labels = {"chrome": "Chrome", "msedge": "Edge"}
    builtin = "可用" if status["builtin"] else "未安裝（可按右側下載）"
    system = "、".join(labels.get(name, name) for name in status["system"]) or "未偵測到"
    return f"內建 Chromium：{builtin}｜系統：{system}"


class TimePickerDialog(MessageBoxBase):
    """選擇每日簽到時間。"""

    def __init__(self, current: str = "09:00", parent=None) -> None:
        super().__init__(parent)
        self.titleLabel = SubtitleLabel("每日自動簽到時間", self)
        self.viewLayout.addWidget(self.titleLabel)
        row = QHBoxLayout()
        self.hourSpin = SpinBox(self)
        self.hourSpin.setRange(0, 23)
        self.minuteSpin = SpinBox(self)
        self.minuteSpin.setRange(0, 59)
        try:
            hour, minute = (int(x) for x in current.split(":"))
        except Exception:
            hour, minute = 9, 0
        self.hourSpin.setValue(hour)
        self.minuteSpin.setValue(minute)
        row.addWidget(CaptionLabel("時", self))
        row.addWidget(self.hourSpin)
        row.addSpacing(12)
        row.addWidget(CaptionLabel("分", self))
        row.addWidget(self.minuteSpin)
        row.addStretch(1)
        self.viewLayout.addLayout(row)
        self.yesButton.setText("確定")
        self.cancelButton.setText("取消")
        self.widget.setMinimumWidth(360)

    def value(self) -> str:
        return f"{self.hourSpin.value():02d}:{self.minuteSpin.value():02d}"


class SettingsPage(SmoothScrollArea):
    """設定頁。`on_change(key, value)` 會在任一設定變更時被呼叫。"""

    def __init__(self, cfg, on_change: Callable[[str, Any], None], parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        make_background_transparent(self)

        self.cfg = cfg
        self._on_change = on_change
        self._loading = True
        self._cards: list[tuple[SettingCard, SettingCardGroup]] = []

        container = QWidget()
        container.setObjectName("settingsContainer")
        make_background_transparent(container)
        self.setWidget(container)
        from PySide6.QtWidgets import QVBoxLayout

        self.vBox = QVBoxLayout(container)
        self.vBox.setContentsMargins(28, 24, 28, 28)
        self.vBox.setSpacing(18)

        self._build_general()
        self._build_checkin()
        self._build_account()
        self._build_notify()
        self._build_advanced()
        self.vBox.addStretch(1)
        self.reload(cfg)

    # ------------------------------------------------------------------
    def _group(self, title: str) -> SettingCardGroup:
        group = SettingCardGroup(title, self)
        self.vBox.addWidget(group)
        return group

    def _add(self, group: SettingCardGroup, card: SettingCard, key: str | None = None,
             signal: str | None = None) -> SettingCard:
        group.addSettingCard(card)
        self._cards.append((card, group))
        if key and signal:
            getattr(card, signal).connect(lambda value, k=key: self._changed(k, value))
        return card

    def _changed(self, key: str, value: Any) -> None:
        if self._loading:
            return
        self._on_change(key, value)

    # --- 一般 ----------------------------------------------------------
    def _build_general(self) -> None:
        group = self._group("一般設定")
        self.themeCard = self._add(
            group,
            ComboCard(
                FluentIcon.BRUSH,
                "介面主題",
                [
                    ("跟隨系統", THEME_SYSTEM),
                    ("淺色", THEME_LIGHT),
                    ("深色（預設）", THEME_DARK),
                ],
                "變更後立即套用",
                self,
            ),
            "theme",
            "valueChanged",
        )
        self.autostartCard = self._add(
            group,
            SwitchCard(FluentIcon.POWER_BUTTON, "開機自啓動", "登入 Windows 後自動在背景執行", self),
            "autostart",
            "checkedChanged",
        )
        self.startMinimizedCard = self._add(
            group,
            SwitchCard(FluentIcon.MINIMIZE, "啟動時縮到系統匣", "開機自啓動時不顯示主視窗", self),
            "start_minimized",
            "checkedChanged",
        )
        self.closeToTrayCard = self._add(
            group,
            SwitchCard(FluentIcon.CLOSE, "關閉視窗時縮到系統匣", "按右上角 X 不會結束程式", self),
            "close_to_tray",
            "checkedChanged",
        )
        self.singleInstanceCard = self._add(
            group,
            SwitchCard(FluentIcon.APPLICATION, "只允許一個實例", "避免同時執行多份造成重複簽到", self),
            "single_instance",
            "checkedChanged",
        )

    # --- 簽到 ----------------------------------------------------------
    def _build_checkin(self) -> None:
        group = self._group("簽到設定")

        self.timeCard = PushSettingCard(
            "選擇時間", FluentIcon.CALENDAR, "每日自動簽到時間", "目前：09:00", self
        )
        self.timeCard.clicked.connect(self._pick_time)
        group.addSettingCard(self.timeCard)
        self._cards.append((self.timeCard, group))

        self.jitterCard = self._add(
            group,
            SpinCard(
                FluentIcon.SYNC,
                "隨機延遲",
                "在設定時間前後隨機浮動，避免每天固定時間觸發風控",
                minimum=0,
                maximum=180,
                suffix="分鐘",
                parent=self,
            ),
            "jitter_minutes",
            "valueChanged",
        )
        self.catchupCard = self._add(
            group,
            SwitchCard(
                FluentIcon.HISTORY,
                "啟動時補簽",
                "開啟程式時若今日尚未簽到，立即執行一次",
                self,
            ),
            "run_on_start_if_missed",
            "checkedChanged",
        )
        self.timeoutCard = self._add(
            group,
            SpinCard(
                FluentIcon.STOP_WATCH,
                "頁面逾時",
                "載入 MiniMax 頁面與等待回應的最長時間",
                minimum=15,
                maximum=600,
                suffix="秒",
                parent=self,
            ),
            "timeout_seconds",
            "valueChanged",
        )
        self.retryCard = self._add(
            group,
            SpinCard(
                FluentIcon.UPDATE,
                "失敗重試次數",
                "當日簽到失敗後最多再嘗試幾次",
                minimum=0,
                maximum=10,
                suffix="次",
                parent=self,
            ),
            "retry_times",
            "valueChanged",
        )
        self.retryIntervalCard = self._add(
            group,
            SpinCard(
                FluentIcon.HISTORY,
                "重試間隔",
                "兩次重試之間等待的時間",
                minimum=1,
                maximum=720,
                suffix="分鐘",
                parent=self,
            ),
            "retry_interval_minutes",
            "valueChanged",
        )
        self.headlessCard = self._add(
            group,
            SwitchCard(
                FluentIcon.VIEW,
                "無頭模式（不顯示瀏覽器視窗）",
                "背景靜默執行；若被風控阻擋可關閉此選項改用顯示視窗",
                self,
            ),
            "headless",
            "checkedChanged",
        )
        self.fallbackCard = self._add(
            group,
            SwitchCard(
                FluentIcon.SYNC,
                "無頭失敗時改用顯示視窗重試",
                "提高成功率，但執行時會短暫出現瀏覽器視窗",
                self,
            ),
            "fallback_headed",
            "checkedChanged",
        )
        self.keepBrowserCard = self._add(
            group,
            SwitchCard(
                FluentIcon.DEVELOPER_TOOLS,
                "執行後保留瀏覽器視窗",
                "除錯用：方便觀察簽到過程",
                self,
            ),
            "keep_browser_open",
            "checkedChanged",
        )

    # --- 帳號 ----------------------------------------------------------
    def _build_account(self) -> None:
        group = self._group("帳號設定")
        self.concurrentCard = self._add(
            group,
            SpinCard(
                FluentIcon.PEOPLE,
                "同時處理帳號數",
                "建議維持 1（依序執行），一次處理多個帳號較容易被風控",
                minimum=1,
                maximum=3,
                suffix="個",
                parent=self,
            ),
            "concurrent_accounts",
            "valueChanged",
        )
        self.encryptCard = self._add(
            group,
            SwitchCard(
                FluentIcon.FINGERPRINT,
                "加密儲存登入 session",
                "使用 Windows DPAPI 加密（僅本機使用者可解密）；關閉後改存明文 JSON",
                self,
            ),
            "encrypt_sessions",
            "checkedChanged",
        )
        self.openAccountsCard = PushSettingCard(
            "開啟資料夾", FluentIcon.FOLDER, "帳號資料目錄", str(paths.accounts_dir()), self
        )
        self.openAccountsCard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.accounts_dir())))
        )
        group.addSettingCard(self.openAccountsCard)
        self._cards.append((self.openAccountsCard, group))

        self.clearSessionsCard = PushSettingCard(
            "清除全部", FluentIcon.DELETE, "清除所有登入狀態", "需要重新登入所有帳號", self
        )
        self.clearSessionsCard.clicked.connect(lambda: self._changed("clear_sessions", True))
        group.addSettingCard(self.clearSessionsCard)
        self._cards.append((self.clearSessionsCard, group))

    def _pick_time(self) -> None:
        dialog = TimePickerDialog(self.cfg.daily_time, self.window())
        if dialog.exec():
            value = dialog.value()
            self.cfg.daily_time = value
            self.timeCard.setContent(f"目前：{value}")
            self._changed("daily_time", value)

    # --- 通知 ----------------------------------------------------------
    def _build_notify(self) -> None:
        group = self._group("通知設定")
        self.notifySuccessCard = self._add(
            group,
            SwitchCard(FluentIcon.COMPLETED, "簽到成功通知", "以系統通知顯示獲得的點數", self),
            "notify_success",
            "checkedChanged",
        )
        self.notifyFailCard = self._add(
            group,
            SwitchCard(FluentIcon.RINGER, "簽到失敗通知", "失敗時立即通知，方便手動處理", self),
            "notify_failure",
            "checkedChanged",
        )
        self.notifyReloginCard = self._add(
            group,
            SwitchCard(FluentIcon.PEOPLE, "需要重新登入時通知", "session 過期時提醒重新登入", self),
            "notify_relogin",
            "checkedChanged",
        )

    # --- 進階 ----------------------------------------------------------
    def _build_advanced(self) -> None:
        group = self._group("進階設定")
        self.browserCard = self._add(
            group,
            ComboCard(
                FluentIcon.GLOBE,
                "瀏覽器核心",
                [(BROWSER_LABELS[c], c) for c in BROWSER_CHOICES],
                "改用系統已安裝的 Chrome／Edge 有時能降低風控機率",
                self,
            ),
            "browser_channel",
            "valueChanged",
        )

        self.browserStatusCard = PushSettingCard(
            "下載核心",
            FluentIcon.DOWNLOAD,
            "瀏覽器核心狀態",
            browser_status_text(),
            self,
        )
        self.browserStatusCard.clicked.connect(lambda: self._changed("download_browser", True))
        group.addSettingCard(self.browserStatusCard)
        self._cards.append((self.browserStatusCard, group))
        self.proxyCard = self._add(
            group,
            TextCard(
                FluentIcon.WIFI,
                "代理伺服器",
                "例如 http://127.0.0.1:7890（留空表示不使用）",
                placeholder="留空表示不使用",
                parent=self,
            ),
            "proxy",
            "textChanged",
        )
        self.userAgentCard = self._add(
            group,
            TextCard(
                FluentIcon.IOT,
                "自訂 User-Agent",
                "留空則使用內建的 Chrome UA",
                placeholder="留空使用預設",
                parent=self,
            ),
            "custom_user_agent",
            "textChanged",
        )
        self.logLevelCard = self._add(
            group,
            ComboCard(
                FluentIcon.DOCUMENT,
                "日誌等級",
                [(level, level) for level in LOG_LEVELS],
                "調整寫入日誌的詳細程度",
                self,
            ),
            "log_level",
            "valueChanged",
        )
        self.logDaysCard = self._add(
            group,
            SpinCard(
                FluentIcon.SAVE,
                "日誌保留天數",
                "超過天數的舊日誌會自動刪除",
                minimum=1,
                maximum=365,
                suffix="天",
                parent=self,
            ),
            "log_days",
            "valueChanged",
        )
        self.driftCard = self._add(
            group,
            SpinCard(
                FluentIcon.SEARCH,
                "改版偵測門檻",
                "連續幾次找不到簽到介面就提示「應用可能已過期」",
                minimum=1,
                maximum=30,
                suffix="次",
                parent=self,
            ),
            "drift_threshold",
            "valueChanged",
        )
        self.openLogsCard = PushSettingCard(
            "開啟資料夾", FluentIcon.FOLDER, "日誌目錄", str(paths.logs_dir()), self
        )
        self.openLogsCard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.logs_dir())))
        )
        group.addSettingCard(self.openLogsCard)
        self._cards.append((self.openLogsCard, group))

        # --- 檔案位置（Roaming 設定 / Local 資料） ------------------------
        storage = self._group("檔案位置")
        self.roamingCard = PushSettingCard(
            "開啟資料夾",
            FluentIcon.FOLDER,
            "設定檔目錄（Roaming）",
            str(paths.roaming_dir()),
            self,
        )
        self.roamingCard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.roaming_dir())))
        )
        storage.addSettingCard(self.roamingCard)
        self._cards.append((self.roamingCard, storage))

        self.localCard = PushSettingCard(
            "開啟資料夾",
            FluentIcon.FOLDER,
            "本機資料（Local）",
            "帳號登入狀態、日誌、診斷檔（DPAPI 加密僅本機可用，故不隨帳號漫遊）",
            self,
        )
        self.localCard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.local_dir())))
        )
        storage.addSettingCard(self.localCard)
        self._cards.append((self.localCard, storage))

        self.openDiagCard = PushSettingCard(
            "開啟資料夾",
            FluentIcon.DEVELOPER_TOOLS,
            "診斷資料目錄",
            "內含每次簽到前後的頁面與 API 擷取結果",
            self,
        )
        self.openDiagCard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.diagnostics_dir())))
        )
        storage.addSettingCard(self.openDiagCard)
        self._cards.append((self.openDiagCard, storage))

        self.clearDataCard = PushSettingCard(
            "清除資料",
            FluentIcon.DELETE,
            "清除所有本機資料",
            "刪除日誌與診斷檔（不影響設定與帳號）",
            self,
        )
        self.clearDataCard.clicked.connect(lambda: self._changed("clear_local_data", True))
        storage.addSettingCard(self.clearDataCard)
        self._cards.append((self.clearDataCard, storage))

        # --- 關於 ---------------------------------------------------------
        about = self._group("關於")
        self.versionCard = PushSettingCard(
            f"v{APP_VERSION}",
            FluentIcon.INFO,
            APP_NAME_CN,
            f"選擇器包 v{SELECTOR_PACK_VERSION}｜"
            + ("可攜模式" if paths.is_portable() else f"安裝位置 {paths.install_dir()}"),
            self,
        )
        self.versionCard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.install_dir())))
        )
        about.addSettingCard(self.versionCard)
        self._cards.append((self.versionCard, about))

        self.licenseCard = PushSettingCard(
            "檢視授權",
            FluentIcon.CERTIFICATE,
            "授權條款：GNU GPL v3",
            "本程式使用 PySide6-Fluent-Widgets（GPL-3.0），因此同樣以 GPL-3.0 發佈",
            self,
        )
        self.licenseCard.clicked.connect(self._open_license)
        about.addSettingCard(self.licenseCard)
        self._cards.append((self.licenseCard, about))

        self.noticesCard = PushSettingCard(
            "檢視清單",
            FluentIcon.DOCUMENT,
            "第三方元件授權",
            "PySide6／Qt、PySide6-Fluent-Widgets、Playwright、loguru、pywin32",
            self,
        )
        self.noticesCard.clicked.connect(self._open_notices)
        about.addSettingCard(self.noticesCard)
        self._cards.append((self.noticesCard, about))

    def _open_license(self) -> None:
        path = paths.license_file()
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QDesktopServices.openUrl(QUrl("https://www.gnu.org/licenses/gpl-3.0.html"))

    def _open_notices(self) -> None:
        path = paths.notices_file()
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

        # （日誌／診斷／關於 已移至「檔案位置」與「關於」群組）

    # ------------------------------------------------------------------
    def reload(self, cfg) -> None:
        """把設定值載入卡片（不觸發 on_change）。"""
        self._loading = True
        try:
            self.timeCard.setContent(f"目前：{cfg.daily_time}")
            for key, card in self._bindings().items():
                value = getattr(cfg, key, None)
                if value is not None:
                    card.setValue(value)
        finally:
            self._loading = False

    def set_daily_time(self, value: str) -> None:
        self.timeCard.setContent(f"目前：{value}")

    def _bindings(self) -> dict[str, Any]:
        return {
            "theme": self.themeCard,
            "autostart": self.autostartCard,
            "start_minimized": self.startMinimizedCard,
            "close_to_tray": self.closeToTrayCard,
            "single_instance": self.singleInstanceCard,
            "jitter_minutes": self.jitterCard,
            "run_on_start_if_missed": self.catchupCard,
            "timeout_seconds": self.timeoutCard,
            "retry_times": self.retryCard,
            "retry_interval_minutes": self.retryIntervalCard,
            "headless": self.headlessCard,
            "fallback_headed": self.fallbackCard,
            "keep_browser_open": self.keepBrowserCard,
            "concurrent_accounts": self.concurrentCard,
            "encrypt_sessions": self.encryptCard,
            "notify_success": self.notifySuccessCard,
            "notify_failure": self.notifyFailCard,
            "notify_relogin": self.notifyReloginCard,
            "browser_channel": self.browserCard,
            "proxy": self.proxyCard,
            "custom_user_agent": self.userAgentCard,
            "log_level": self.logLevelCard,
            "log_days": self.logDaysCard,
            "drift_threshold": self.driftCard,
        }

    def apply_filter(self, keyword: str) -> None:
        """依關鍵字隱藏不相關的設定卡片（對應標題列的「搜尋設定」）。"""
        keyword = (keyword or "").strip().lower()
        group_hits: dict[int, bool] = {}
        for card, group in self._cards:
            title = card.titleLabel.text() if hasattr(card, "titleLabel") else ""
            content = card.contentLabel.text() if hasattr(card, "contentLabel") else ""
            matched = keyword in f"{title} {content}".lower() if keyword else True
            card.setVisible(matched)
            group_hits[id(group)] = group_hits.get(id(group), False) or matched
        for _card, group in self._cards:
            group.setVisible(group_hits.get(id(group), True))