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
    LOG_LEVELS,
    THEME_DARK,
    THEME_LIGHT,
    THEME_SYSTEM,
)
from app.constants import APP_NAME, APP_NAME_CN, APP_VERSION, SELECTOR_PACK_VERSION
from app.ui.components import ComboCard, SpinCard, SwitchCard, TextCard, make_background_transparent
from app.i18n import t


def browser_status_text() -> str:
    """瀏覽器核心狀態說明（給設定卡片顯示）。"""
    from app.core.browser import browser_status
    from app.i18n import t

    status = browser_status()
    labels = {"chrome": "Chrome", "msedge": "Edge"}
    builtin = t("settings.browser.ok") if status["builtin"] else t("settings.browser.missing")
    system = "、".join(labels.get(name, name) for name in status["system"]) or t("settings.browser.none")
    return t("settings.browser.status", builtin=builtin, system=system)


class TimePickerDialog(MessageBoxBase):
    """選擇每日簽到時間。"""

    def __init__(self, current: str = "09:00", parent=None) -> None:
        super().__init__(parent)
        from app.i18n import t

        self.titleLabel = SubtitleLabel(t("settings.time.title"), self)
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
        row.addWidget(CaptionLabel(t("settings.time.hour"), self))
        row.addWidget(self.hourSpin)
        row.addSpacing(12)
        row.addWidget(CaptionLabel(t("settings.time.minute"), self))
        row.addWidget(self.minuteSpin)
        row.addStretch(1)
        self.viewLayout.addLayout(row)
        self.yesButton.setText(t("settings.time.ok"))
        self.cancelButton.setText(t("settings.time.cancel"))
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
        group = self._group(t("settings.group.general"))
        self.themeCard = self._add(
            group,
            ComboCard(
                FluentIcon.BRUSH,
                t("settings.theme"),
                [
                    (t("settings.theme.follow"), THEME_SYSTEM),
                    (t("settings.theme.light"), THEME_LIGHT),
                    (t("settings.theme.dark"), THEME_DARK),
                ],
                t("settings.theme.hint"),
                self,
            ),
            "theme",
            "valueChanged",
        )
        from app.i18n import LANGUAGE_CHOICES, LANGUAGE_LABELS

        self.languageCard = self._add(
            group,
            ComboCard(
                FluentIcon.GLOBE,
                t("settings.language"),
                [(LANGUAGE_LABELS[c], c) for c in LANGUAGE_CHOICES],
                t("settings.language.hint"),
                self,
            ),
            "language",
            "valueChanged",
        )
        self.autostartCard = self._add(
            group,
            SwitchCard(FluentIcon.POWER_BUTTON, t("settings.autostart"), t("settings.autostart.hint"), self),
            "autostart",
            "checkedChanged",
        )
        self.startMinimizedCard = self._add(
            group,
            SwitchCard(FluentIcon.MINIMIZE, t("settings.start_minimized"), t("settings.start_minimized.hint"), self),
            "start_minimized",
            "checkedChanged",
        )
        self.minimizeOnManualLaunchCard = self._add(
            group,
            SwitchCard(FluentIcon.HIDE, t("settings.minimize_manual"), t("settings.minimize_manual.hint"), self),
            "minimize_on_manual_launch",
            "checkedChanged",
        )
        self.closeToTrayCard = self._add(
            group,
            SwitchCard(FluentIcon.CLOSE, t("settings.close_to_tray"), t("settings.close_to_tray.hint"), self),
            "close_to_tray",
            "checkedChanged",
        )
        self.singleInstanceCard = self._add(
            group,
            SwitchCard(FluentIcon.APPLICATION, t("settings.single_instance"), t("settings.single_instance.hint"), self),
            "single_instance",
            "checkedChanged",
        )

    # --- 簽到 ----------------------------------------------------------
    def _build_checkin(self) -> None:
        group = self._group(t("settings.group.checkin"))

        self.timeCard = PushSettingCard(
            t("settings.daily_time.pick"), FluentIcon.CALENDAR, t("settings.daily_time"), t("settings.daily_time.now", value="09:00"), self
        )
        self.timeCard.clicked.connect(self._pick_time)
        group.addSettingCard(self.timeCard)
        self._cards.append((self.timeCard, group))

        self.jitterCard = self._add(
            group,
            SpinCard(
                FluentIcon.SYNC,
                t("settings.jitter"),
                t("settings.jitter.hint"),
                minimum=0,
                maximum=180,
                suffix=t("settings.jitter.suffix"),
                parent=self,
            ),
            "jitter_minutes",
            "valueChanged",
        )
        self.catchupCard = self._add(
            group,
            SwitchCard(
                FluentIcon.HISTORY,
                t("settings.catchup"),
                t("settings.catchup.hint"),
                self,
            ),
            "run_on_start_if_missed",
            "checkedChanged",
        )
        self.timeoutCard = self._add(
            group,
            SpinCard(
                FluentIcon.STOP_WATCH,
                t("settings.timeout"),
                t("settings.timeout.hint"),
                minimum=15,
                maximum=600,
                suffix=t("settings.timeout.suffix"),
                parent=self,
            ),
            "timeout_seconds",
            "valueChanged",
        )
        self.retryCard = self._add(
            group,
            SpinCard(
                FluentIcon.UPDATE,
                t("settings.retry"),
                t("settings.retry.hint"),
                minimum=0,
                maximum=10,
                suffix=t("settings.retry.suffix"),
                parent=self,
            ),
            "retry_times",
            "valueChanged",
        )
        self.retryIntervalCard = self._add(
            group,
            SpinCard(
                FluentIcon.HISTORY,
                t("settings.retry_interval"),
                t("settings.retry_interval.hint"),
                minimum=1,
                maximum=720,
                suffix=t("settings.retry_interval.suffix"),
                parent=self,
            ),
            "retry_interval_minutes",
            "valueChanged",
        )
        self.headlessCard = self._add(
            group,
            SwitchCard(
                FluentIcon.VIEW,
                t("settings.headless"),
                t("settings.headless.hint"),
                self,
            ),
            "headless",
            "checkedChanged",
        )
        self.fallbackCard = self._add(
            group,
            SwitchCard(
                FluentIcon.SYNC,
                t("settings.fallback"),
                t("settings.fallback.hint"),
                self,
            ),
            "fallback_headed",
            "checkedChanged",
        )
        self.keepBrowserCard = self._add(
            group,
            SwitchCard(
                FluentIcon.DEVELOPER_TOOLS,
                t("settings.keep_browser"),
                t("settings.keep_browser.hint"),
                self,
            ),
            "keep_browser_open",
            "checkedChanged",
        )

    # --- 帳號 ----------------------------------------------------------
    def _build_account(self) -> None:
        group = self._group(t("settings.group.accounts"))
        self.concurrentCard = self._add(
            group,
            SpinCard(
                FluentIcon.PEOPLE,
                t("settings.concurrent"),
                t("settings.concurrent.hint"),
                minimum=1,
                maximum=3,
                suffix=t("settings.concurrent.suffix"),
                parent=self,
            ),
            "concurrent_accounts",
            "valueChanged",
        )
        self.encryptCard = self._add(
            group,
            SwitchCard(
                FluentIcon.FINGERPRINT,
                t("settings.encrypt"),
                t("settings.encrypt.hint"),
                self,
            ),
            "encrypt_sessions",
            "checkedChanged",
        )
        self.openAccountsCard = PushSettingCard(
            t("settings.open_folder"), FluentIcon.FOLDER, t("settings.accounts_dir"), str(paths.accounts_dir()), self
        )
        self.openAccountsCard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.accounts_dir())))
        )
        group.addSettingCard(self.openAccountsCard)
        self._cards.append((self.openAccountsCard, group))

        self.clearSessionsCard = PushSettingCard(
            t("settings.clear_sessions.all"), FluentIcon.DELETE, t("settings.clear_sessions"), t("settings.clear_sessions.hint"), self
        )
        self.clearSessionsCard.clicked.connect(lambda: self._changed("clear_sessions", True))
        group.addSettingCard(self.clearSessionsCard)
        self._cards.append((self.clearSessionsCard, group))

    def _pick_time(self) -> None:
        dialog = TimePickerDialog(self.cfg.daily_time, self.window())
        if dialog.exec():
            value = dialog.value()
            self.cfg.daily_time = value
            self.timeCard.setContent(t("settings.daily_time.now", value=value))
            self._changed("daily_time", value)

    # --- 通知 ----------------------------------------------------------
    def _build_notify(self) -> None:
        group = self._group(t("settings.group.notify"))
        self.notifySuccessCard = self._add(
            group,
            SwitchCard(FluentIcon.COMPLETED, t("settings.notify.success"), t("settings.notify.success.hint"), self),
            "notify_success",
            "checkedChanged",
        )
        self.notifyFailCard = self._add(
            group,
            SwitchCard(FluentIcon.RINGER, t("settings.notify.fail"), t("settings.notify.fail.hint"), self),
            "notify_failure",
            "checkedChanged",
        )
        self.notifyReloginCard = self._add(
            group,
            SwitchCard(FluentIcon.PEOPLE, t("settings.notify.relogin"), t("settings.notify.relogin.hint"), self),
            "notify_relogin",
            "checkedChanged",
        )
        self.notifyMinimizeHintCard = self._add(
            group,
            SwitchCard(FluentIcon.HOME, t("settings.notify.minimize"), t("settings.notify.minimize.hint"), self),
            "notify_minimize_hint",
            "checkedChanged",
        )

    # --- 進階 ----------------------------------------------------------
    def _build_advanced(self) -> None:
        from app.config import browser_label

        group = self._group(t("settings.group.advanced"))
        self.browserCard = self._add(
            group,
            ComboCard(
                FluentIcon.GLOBE,
                t("settings.browser"),
                [(browser_label(c), c) for c in BROWSER_CHOICES],
                t("settings.browser.hint"),
                self,
            ),
            "browser_channel",
            "valueChanged",
        )

        self.browserStatusCard = PushSettingCard(
            t("settings.browser.download"),
            FluentIcon.DOWNLOAD,
            t("settings.browser.status"),
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
                t("settings.proxy"),
                t("settings.proxy.hint"),
                placeholder=t("settings.proxy.placeholder"),
                parent=self,
            ),
            "proxy",
            "textChanged",
        )
        self.userAgentCard = self._add(
            group,
            TextCard(
                FluentIcon.IOT,
                t("settings.user_agent"),
                t("settings.user_agent.hint"),
                placeholder=t("settings.user_agent.placeholder"),
                parent=self,
            ),
            "custom_user_agent",
            "textChanged",
        )
        self.logLevelCard = self._add(
            group,
            ComboCard(
                FluentIcon.DOCUMENT,
                t("settings.log_level"),
                [(level, level) for level in LOG_LEVELS],
                t("settings.log_level.hint"),
                self,
            ),
            "log_level",
            "valueChanged",
        )
        self.logDaysCard = self._add(
            group,
            SpinCard(
                FluentIcon.SAVE,
                t("settings.log_days"),
                t("settings.log_days.hint"),
                minimum=1,
                maximum=365,
                suffix=t("settings.log_days.suffix"),
                parent=self,
            ),
            "log_days",
            "valueChanged",
        )
        self.driftCard = self._add(
            group,
            SpinCard(
                FluentIcon.SEARCH,
                t("settings.drift"),
                t("settings.drift.hint"),
                minimum=1,
                maximum=30,
                suffix=t("settings.drift.suffix"),
                parent=self,
            ),
            "drift_threshold",
            "valueChanged",
        )
        self.openLogsCard = PushSettingCard(
            t("settings.open_folder"), FluentIcon.FOLDER, t("settings.logs_dir"), str(paths.logs_dir()), self
        )
        self.openLogsCard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.logs_dir())))
        )
        group.addSettingCard(self.openLogsCard)
        self._cards.append((self.openLogsCard, group))

        # --- 檔案位置（Roaming 設定 / Local 資料） ------------------------
        storage = self._group(t("settings.files.group"))
        self.roamingCard = PushSettingCard(
            t("settings.open_folder"),
            FluentIcon.FOLDER,
            t("settings.roaming_dir"),
            str(paths.roaming_dir()),
            self,
        )
        self.roamingCard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.roaming_dir())))
        )
        storage.addSettingCard(self.roamingCard)
        self._cards.append((self.roamingCard, storage))

        self.localCard = PushSettingCard(
            t("settings.open_folder"),
            FluentIcon.FOLDER,
            t("settings.local_dir"),
            t("settings.local_dir.hint"),
            self,
        )
        self.localCard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.local_dir())))
        )
        storage.addSettingCard(self.localCard)
        self._cards.append((self.localCard, storage))

        self.openDiagCard = PushSettingCard(
            t("settings.open_folder"),
            FluentIcon.DEVELOPER_TOOLS,
            t("settings.diag_dir"),
            t("settings.diag_dir.hint"),
            self,
        )
        self.openDiagCard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.diagnostics_dir())))
        )
        storage.addSettingCard(self.openDiagCard)
        self._cards.append((self.openDiagCard, storage))

        self.clearDataCard = PushSettingCard(
            t("settings.clear_local.all"),
            FluentIcon.DELETE,
            t("settings.clear_local"),
            t("settings.clear_local.hint"),
            self,
        )
        self.clearDataCard.clicked.connect(lambda: self._changed("clear_local_data", True))
        storage.addSettingCard(self.clearDataCard)
        self._cards.append((self.clearDataCard, storage))

        # --- 關於 ---------------------------------------------------------
        about = self._group(t("settings.about.group"))
        self.versionCard = PushSettingCard(
            f"v{APP_VERSION}",
            FluentIcon.INFO,
            APP_NAME_CN,
            f"選擇器包 v{SELECTOR_PACK_VERSION}｜"
            + (t("settings.about.portable") if paths.is_portable() else t("settings.about.install_at", path=paths.install_dir())),
            self,
        )
        self.versionCard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.install_dir())))
        )
        about.addSettingCard(self.versionCard)
        self._cards.append((self.versionCard, about))

        self.licenseCard = PushSettingCard(
            t("settings.license.open"),
            FluentIcon.CERTIFICATE,
            t("settings.license"),
            "GNU GPL v3",
            self,
        )
        self.licenseCard.clicked.connect(self._open_license)
        about.addSettingCard(self.licenseCard)
        self._cards.append((self.licenseCard, about))

        self.noticesCard = PushSettingCard(
            t("settings.notices.open"),
            FluentIcon.DOCUMENT,
            t("settings.notices"),
            t("settings.notices.hint"),
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
            self.timeCard.setContent(t("settings.time.picked", value=cfg.daily_time))
            for key, card in self._bindings().items():
                value = getattr(cfg, key, None)
                if value is not None:
                    card.setValue(value)
        finally:
            self._loading = False

    def set_daily_time(self, value: str) -> None:
        self.timeCard.setContent(t("settings.time.picked", value=value))

    def _bindings(self) -> dict[str, Any]:
        return {
            "theme": self.themeCard,
            "language": self.languageCard,
            "autostart": self.autostartCard,
            "start_minimized": self.startMinimizedCard,
            "minimize_on_manual_launch": self.minimizeOnManualLaunchCard,
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
            "notify_minimize_hint": self.notifyMinimizeHintCard,
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