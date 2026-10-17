"""主視窗：Fluent 介面（左側導覽 + 卡片式內容 + 標題列搜尋），風格參考 Ghost Downloader。"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from qfluentwidgets import (
    Action,
    BodyLabel,
    FluentIcon as FIF,
    FluentWindow,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    MessageBox,
    MessageBoxBase,
    NavigationItemPosition,
    SubtitleLabel,
    SystemTrayMenu,
    Theme,
    setTheme,
    setThemeColor,
)

from app import paths
from app.config import THEME_DARK, THEME_LIGHT, THEME_SYSTEM, AppConfig
from app.constants import APP_NAME, RunStatus
from app.core import autostart
from app.i18n import t
from app.logger import logger
from app.ui.account_page import AccountPage
from app.ui.components import refresh_page_backgrounds, sync_page_palettes, sync_qt_color_scheme
from app.ui.home_page import HomePage
from app.ui.icon import app_icon
from app.ui.log_page import LogPage
from app.ui.settings_page import SettingsPage
from app.worker import AutomationWorker

THEME_ACCENT = "#0a84ff"


class MainWindow(FluentWindow):
    """主視窗。"""

    def __init__(self, cfg: AppConfig, worker: AutomationWorker) -> None:
        super().__init__()
        self.cfg = cfg
        self.worker = worker
        self._quitting = False
        self._tray_hint_shown = False
        self._pending_update_url = ""
        self._results: dict[str, dict] = {}
        self._shown_once = False  # ?????????--minimized ?????? False?

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(*self._preferred_size())
        # 視窗不可被縮到無法使用（否則內容會被裁切、導覽列被收合）
        self.setMinimumSize(940, 620)
        # 使用 Fluent 官方原生背景機制（Mica 亞克力 + 主題底色）：
        # 實測證實關閉 Mica 又把頁面設為透明，會讓內容區失去底色來源、
        # 在深淺主題下都錯色。官方 FluentWidget 預設就是 Mica 開啟，
        # 主題切換時會自動重設 Mica 材質（見 _onThemeChangedFinished）。

        self.homePage = HomePage(self)
        self.accountPage = AccountPage(self)
        self.logPage = LogPage(self)
        self.settingsPage = SettingsPage(cfg, self._on_setting_changed, self)

        self._init_navigation()
        self._init_title_bar()
        self._init_tray()
        self._connect_signals()
        try:
            self.settingsPage.set_on_update_check(
                lambda: self.worker.request_check_update(manual=True)
            )
        except Exception:
            pass
        self._apply_theme()
        self.refresh_all()

    # ------------------------------------------------------------------
    @staticmethod
    def _preferred_size() -> tuple[int, int]:
        """依螢幕可用範圍決定初始視窗大小（小螢幕也能完整顯示）。"""
        try:
            available = QApplication.primaryScreen().availableGeometry()
            width = max(900, min(1180, available.width() - 80))
            height = max(600, min(780, available.height() - 80))
            return width, height
        except Exception:
            return 1180, 780

    def _init_navigation(self) -> None:
        self.addSubInterface(self.homePage, FIF.HOME, t("nav.overview"))
        self.addSubInterface(self.accountPage, FIF.PEOPLE, t("nav.accounts"))
        self.addSubInterface(self.logPage, FIF.DOCUMENT, t("nav.logs"))
        self.addSubInterface(self.settingsPage, FIF.SETTING, t("nav.settings"))
        try:
            self.navigationInterface.setExpandWidth(210)
            self.navigationInterface.expand(useAni=False)
        except Exception as exc:  # pragma: no cover
            logger.debug(f"展開導覽列失敗：{exc}")
        try:
            self.navigationInterface.addItem(
                routeKey="runNow",
                icon=FIF.PLAY,
                text=t("nav.run_now"),
                onClick=self.run_now,
                position=NavigationItemPosition.BOTTOM,
                tooltip=t("nav.run_now.tooltip"),
            )
        except Exception as exc:  # pragma: no cover
            logger.debug(f"導覽列項目建立失敗：{exc}")

    def _init_title_bar(self) -> None:
        """在標題列加入「搜尋設定」框（Ghost Downloader 的招牌元素）。"""
        self.searchEdit = LineEdit(self.titleBar)
        self.searchEdit.setPlaceholderText(t("search.settings"))
        self.searchEdit.setClearButtonEnabled(True)
        self.searchEdit.setFixedWidth(320)
        self.searchEdit.textChanged.connect(self._on_search)
        try:
            self.searchEdit.addAction(FIF.SEARCH.icon(), LineEdit.LeadingPosition)
        except Exception:
            pass
        try:
            self.titleBar.hBoxLayout.insertWidget(2, self.searchEdit, 0, Qt.AlignCenter)
        except Exception as exc:  # pragma: no cover
            logger.debug(f"標題列搜尋框建立失敗：{exc}")

    def _init_tray(self) -> None:
        self.trayIcon = QSystemTrayIcon(app_icon(), self)
        self.trayIcon.setToolTip(f"{APP_NAME}{t('tray.tooltip')}")
        self.trayMenu = SystemTrayMenu(parent=self)
        self.trayMenu.addAction(Action(FIF.PLAY, t("nav.run_now"), triggered=self.run_now, parent=self))
        self.trayMenu.addAction(
            Action(FIF.HOME, t("tray.show"), triggered=self.show_window, parent=self)
        )
        self.trayMenu.addAction(
            Action(FIF.HISTORY, t("tray.results"), triggered=self.show_results, parent=self)
        )
        self.trayMenu.addAction(
            Action(FIF.FOLDER, t("tray.open_data"), triggered=self.open_data_dir, parent=self)
        )
        self.trayMenu.addSeparator()
        self.trayMenu.addAction(Action(FIF.CLOSE, t("tray.quit"), triggered=self.quit_app, parent=self))
        self.trayIcon.setContextMenu(self.trayMenu)
        self.trayIcon.activated.connect(self._on_tray_activated)
        self.trayIcon.show()

    def _connect_signals(self) -> None:
        self.worker.logMessage.connect(self.logPage.append)
        self.worker.eventReceived.connect(self._on_event)
        self.homePage.runRequested.connect(self.run_now)
        self.homePage.cancelRequested.connect(self.worker.request_cancel)
        self.homePage.probeRequested.connect(lambda: self.worker.request_probe(None))
        self.accountPage.addRequested.connect(self.add_account)
        self.accountPage.reloginRequested.connect(self.worker.request_login)
        self.accountPage.renameRequested.connect(self.rename_account)
        self.accountPage.deleteRequested.connect(self.delete_account)
        self.accountPage.enabledChanged.connect(self.set_account_enabled)

    # --- 事件處理 ------------------------------------------------------
    def _on_event(self, event: str, payload: dict) -> None:
        if event == "starting":
            self.homePage.set_running(False)
        elif event == "ready":
            self.homePage.set_running(False)
            self.refresh_summary(payload.get("next_run_text", ""))
        elif event in ("run_started", "run_state"):
            running = bool(payload.get("running", event == "run_started"))
            self.homePage.set_running(running)
            if not running:
                self.refresh_all()
        elif event == "account_started":
            self.homePage.set_running(True)
        elif event == "account_finished":
            self._results[str(payload.get("account_id"))] = payload
            self.homePage.update_results(list(self._results.values()))
            self.refresh_accounts()
            self._notify_result(payload)
        elif event == "run_finished":
            self.homePage.set_running(False)
            self.refresh_all()
            drift = bool(payload.get("drift_warning"))
            if drift:
                self.info_bar(
                    t("notify.drift.title"),
                    t("notify.drift.body"),
                    ok=False,
                )
        elif event == "login_state":
            self._on_login_state(payload)
        elif event == "accounts_changed":
            self.refresh_all()
        elif event == "probe_finished":
            self.info_bar(
                t("notify.scan.done"),
                t("notify.scan.body", panel=payload.get('panel'), candidates=payload.get('candidates'), matched=payload.get('matched') or t('notify.scan.none')),
                ok=True,
            )
        elif event == "browser_download":
            state = str(payload.get("state", ""))
            if state == "started":
                self.info_bar(
                    t("notify.dl.title"), t("notify.dl.body"), ok=True,
                    duration=8000,
                )
            elif state == "finished":
                self.info_bar(t("notify.dl.done"), str(payload.get("message", "")), ok=True)
            else:
                self.info_bar(t("notify.dl.fail"), str(payload.get("message", "")), ok=False, duration=10000)
        elif event == "error":
            message = str(payload.get("message", ""))
            logger.warning(message)
            self.info_bar(t("notify.error"), message, ok=False)
        elif event == "update_available":
            if self.cfg.notify_update:
                latest = str(payload.get("latest", ""))
                self._pending_update_url = str(payload.get("url", ""))
                self.info_bar(
                    t("notify.update.title"),
                    t("notify.update.body", latest=latest),
                    ok=True,
                    duration=15000,
                )
                self.notify(
                    t("notify.update.title"),
                    t("notify.update.body", latest=latest),
                )
                try:
                    self.settingsPage.set_update_available(latest)
                except Exception:
                    pass
        elif event == "update_checked":
            self.info_bar(
                t("notify.update.latest"),
                t("notify.update.latest.body", current=payload.get("current", "")),
                ok=True,
            )

    def _on_login_state(self, payload: dict) -> None:
        """登入流程各階段的提示（綠色 InfoBar＋帳號卡轉圈圈，不再用藍色 StateToolTip）。"""
        state = str(payload.get("state", ""))
        message = str(payload.get("message", ""))
        account_id = str(payload.get("account_id", ""))

        if state in ("launching", "opening", "waiting_run", "fitting"):
            self.accountPage.set_busy(account_id, True)
        elif state == "ready":
            self.info_bar(
                t("notify.login.title"),
                t("notify.login.body"),
                ok=True,
                duration=10000,
            )
        elif state == "success":
            self.accountPage.set_busy(account_id, False)
            self.info_bar(t("notify.login.success"), f"{payload.get('user_name', '')}{t('notify.login.saved')}", ok=True)
            self.notify(t("notify.login.success"), f"{payload.get('user_name', '')} {t('notify.login.done')}")
            if not bool(payload.get("state_encrypted", True)):
                self.info_bar(
                    t("notify.session.plain.title"),
                    t("notify.session.plain.body"),
                    ok=False,
                    duration=15000,
                )
            self.refresh_all()
        elif state == "failed":
            self.accountPage.set_busy(account_id, False)
            error_kind = str(payload.get("error", ""))
            title = {
                "network": t("login.error.network"),
                "proxy": t("login.error.proxy"),
                "ssl": t("login.error.ssl"),
                "blocked": t("login.error.blocked"),
                "timeout": t("login.error.timeout"),
                "closed": t("login.error.closed"),
                "cancelled": t("login.error.cancelled"),
                "no_browser": t("login.error.nobrowser"),
            }.get(error_kind, t("login.error.other"))
            self.info_bar(title, message, ok=False, duration=12000)
            if error_kind not in ("cancelled",):
                self.notify(title, message, ok=False)

        if account_id:
            self.refresh_accounts()

    def _notify_result(self, payload: dict) -> None:
        status = str(payload.get("status", ""))
        alias = str(payload.get("alias", ""))
        if status == "success" and self.cfg.notify_success:
            self.notify(t("notify.checkin.success"), t("notify.checkin.success.body", alias=alias, points=payload.get('points', 0)))
        elif status in ("failed", "rate_limited", "drift") and self.cfg.notify_failure:
            self.notify(t("notify.checkin.fail"), f"{alias}：{payload.get('message', '')}", ok=False)
        elif status == "need_relogin" and self.cfg.notify_relogin:
            self.notify(t("notify.checkin.relogin"), t("notify.checkin.relogin.body", alias=alias), ok=False)

    def info_bar(self, title: str, content: str, ok: bool = True, duration: int = 5000) -> None:
        (InfoBar.success if ok else InfoBar.warning)(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=duration,
            parent=self,
        )

    def notify(self, title: str, message: str, ok: bool = True) -> None:
        """系統匣通知。"""
        if self.trayIcon.isVisible():
            self.trayIcon.showMessage(
                title,
                message,
                QSystemTrayIcon.Information if ok else QSystemTrayIcon.Warning,
                6000,
            )

    # --- 使用者動作 ----------------------------------------------------
    def run_now(self) -> None:
        if not self.worker.ready:
            self.info_bar(t("notify.engine_starting"), t("notify.engine_wait"), ok=False)
            return
        self.homePage.set_running(True)
        self._results.clear()
        self.worker.request_run("manual")

    def add_account(self) -> None:
        accounts = self.worker.accounts
        account = accounts.add()
        self.refresh_all()
        self.info_bar(
            t("notify.account.added"),
            t("notify.account.added.body"),
            duration=8000,
        )
        self.worker.request_login(account.id)

    def rename_account(self, account_id: str) -> None:
        account = self.worker.accounts.get(account_id)
        if account is None:
            return
        # 必須用 MessageBoxBase（提供 viewLayout 給自訂輸入框）。
        # MessageBox 只有 textLayout、沒有 viewLayout，對它呼叫
        # box.viewLayout.addWidget() 會丟 AttributeError；舊版把這段
        # 包在 try/except: pass 裡，導致輸入框從未加入對話框，使用者
        # 看不到輸入框、按「確定」只會用舊別名（edit.text() 仍是預設值）重新命名。
        box = MessageBoxBase(self)
        title = SubtitleLabel(t("notify.account.rename.title"))
        body = BodyLabel(t("notify.account.rename.body"))
        body.setWordWrap(True)
        edit = LineEdit()
        edit.setText(account.alias)
        edit.setPlaceholderText(t("notify.account.rename.ph"))
        edit.setClearButtonEnabled(True)
        box.viewLayout.addWidget(title)
        box.viewLayout.addWidget(body)
        box.viewLayout.addWidget(edit)
        box.yesButton.setText(t("notify.account.rename.ok"))
        box.cancelButton.setText(t("notify.account.rename.cancel"))
        box.widget.setMinimumWidth(360)
        # 讓輸入框一開對話框就聚焦並全選，方便直接改寫。
        edit.setFocus()
        edit.selectAll()
        # exec() 回傳 QDialog.Accepted(1)／Rejected(0)；按「確定」才繼續。
        if not box.exec():
            return
        ok, reason = self.worker.accounts.rename(account_id, edit.text())
        if not ok:
            self.info_bar(t("notify.account.rename.fail"), reason, ok=False)
            return
        self.refresh_all()
        self.info_bar(t("notify.account.renamed"), edit.text().strip())

    def delete_account(self, account_id: str) -> None:
        account = self.worker.accounts.get(account_id)
        if account is None:
            return
        box = MessageBox(
            t("notify.account.delete.title"),
            t("notify.account.delete.body", name=account.display_name),
            self,
        )
        box.yesButton.setText(t("notify.account.delete.ok"))
        box.cancelButton.setText(t("notify.account.delete.cancel"))
        if not box.exec():
            return
        self.worker.accounts.remove(account_id)
        self._results.pop(account_id, None)
        self.homePage.update_results(list(self._results.values()))
        self.refresh_all()
        self.info_bar(t("notify.account.deleted"), account.display_name)

    def set_account_enabled(self, account_id: str, enabled: bool) -> None:
        self.worker.accounts.update(account_id, enabled=bool(enabled))
        self.refresh_accounts()
        self.refresh_summary()
        logger.info(f"{'啟用' if enabled else '停用'}帳號：{account_id[:6]}")

    def show_window(self) -> None:
        # 自啟動 --minimized 時 hide() 得太早，主題尚未套用造成透明鬼影；
        # 先補主題再顯示，確保從托盤還原時底色正確。
        try:
            self._apply_theme()
        except Exception:
            pass
        # ????????????????showNormal ???? showEvent?
        # ????????????????
        first_show = not getattr(self, "_shown_once", True)
        self.showNormal()
        if first_show:
            # ???????????????????_preferred_size ???
            # ??????????????????????????????
            # ?????????????????????????????
            #??????????????????
            try:
                pref_w, pref_h = self._preferred_size()
                if self.width() < pref_w or self.height() < pref_h:
                    self.resize(max(self.width(), pref_w), max(self.height(), pref_h))
                layout = self.layout()
                if layout is not None:
                    layout.activate()
                self.update()
            except Exception:
                pass
        self.activateWindow()
        self.raise_()

    def showEvent(self, event) -> None:  # noqa: N802 (Qt ????)
        super().showEvent(event)
        self._shown_once = True

    def show_results(self) -> None:
        self.show_window()
        self.switchTo(self.homePage)

    def open_data_dir(self) -> None:
        """開啟本機資料目錄（帳號 session、日誌、診斷）。"""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.local_dir())))

    def quit_app(self) -> None:
        self._quitting = True
        logger.info("正在結束程式…")
        self.cfg.save()
        self.worker.request_shutdown()
        if not self.worker.wait(10000):
            self.worker.terminate()
        self.trayIcon.hide()
        QApplication.quit()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        if self._quitting:
            super().closeEvent(event)
            return
        event.ignore()
        if self.cfg.close_to_tray:
            self.hide()
            if not self._tray_hint_shown and self.cfg.notify_minimize_hint:
                self._tray_hint_shown = True
                self.notify_minimize_hint()
        else:
            self.quit_app()

    def notify_minimize_hint(self) -> None:
        """縮到托盤時的「仍在背景執行」提示：QMessageBox＋「不再顯示」勾選框。

        Windows 的托盤氣泡（QSystemTrayIcon.showMessage）不支援自訂按鈕，
        所以用人性化的對話框承載「不再顯示」選項；勾選後寫入設定並持久化。
        """
        from PySide6.QtWidgets import QCheckBox

        box = MessageBox(t("tray.still_running.title"), t("tray.still_running.body"), self)
        box.yesButton.setText(t("tray.still_running.ok"))
        box.cancelButton.hide()
        hint = QCheckBox(t("tray.still_running.never"), box)
        try:
            box.viewLayout.addWidget(hint)
        except Exception:
            pass
        box.exec()
        try:
            if hint.isChecked() and self.cfg.notify_minimize_hint:
                self.cfg.notify_minimize_hint = False
                self.cfg.save()
                try:
                    self.settingsPage.reload(self.cfg)
                except Exception:
                    pass
                logger.info("已關閉「縮到托盤時顯示提示」")
        except Exception:
            pass

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.show_window()

    def _on_search(self, text: str) -> None:
        self.settingsPage.apply_filter(text)
        if text.strip():
            self.switchTo(self.settingsPage)

    # --- 設定 ----------------------------------------------------------
    def _on_setting_changed(self, key: str, value: Any) -> None:
        if key == "clear_sessions":
            self._confirm_clear_sessions()
            return
        if key == "clear_local_data":
            self._confirm_clear_local_data()
            return
        if key == "download_browser":
            self.worker.request_download_browser()
            return
        setattr(self.cfg, key, value)
        self.cfg.normalize()
        self.cfg.save()
        if key == "theme":
            self._apply_theme()
        elif key == "language":
            from app.i18n import set_language

            set_language(str(value))
            self.info_bar(t("notify.lang.changed"), t("notify.lang.restart"), duration=8000)
        elif key == "autostart":
            if not autostart.apply(bool(value)):
                self.info_bar(t("notify.setting.fail"), t("notify.setting.fail.body"), ok=False)
        elif key == "daily_time":
            self.refresh_summary()
        logger.info(f"設定已更新：{key} = {value}")

    def _confirm_clear_sessions(self) -> None:
        box = MessageBox(t("notify.sessions.clear.title"), t("notify.sessions.clear.body"), self)
        box.yesButton.setText(t("notify.sessions.clear.ok"))
        box.cancelButton.setText(t("notify.sessions.clear.cancel"))
        if not box.exec():
            self.settingsPage.reload(self.cfg)
            return
        manager = self.worker.accounts
        for account in manager.accounts:
            manager.clear_state(account)
            manager.update(account.id, persist=False, last_status="", last_message=t("accounts.card.not_run"))
        manager.save()
        self._results.clear()
        self.refresh_all()
        self.info_bar(t("notify.sessions.cleared"), t("notify.sessions.cleared.body"))

    def _confirm_clear_local_data(self) -> None:
        """清除日誌與診斷檔（保留設定與帳號）。"""
        box = MessageBox(
            t("notify.local.clear.title"),
            t("notify.local.clear.body", folders=f"{paths.logs_dir()}\n{paths.diagnostics_dir()}"),
            self,
        )
        box.yesButton.setText(t("notify.local.clear.ok"))
        box.cancelButton.setText(t("notify.local.clear.cancel"))
        if not box.exec():
            return
        removed = 0
        import shutil

        for folder in (paths.logs_dir(), paths.diagnostics_dir()):
            for item in folder.iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink()
                    removed += 1
                except OSError:
                    continue
        self.info_bar(t("notify.local.cleared"), t("notify.local.cleared.body", count=removed))
        logger.info(f"已清除本機資料：{removed} 個項目")

    def _apply_theme(self) -> None:
        """套用介面主題。

        除了 qfluentwidgets 的 `setTheme`，還必須同步 Qt 的 colorScheme：
        Qt 6.8+ 會自動跟隨 Windows 的深色模式，若不覆寫，使用原生調色盤繪製的
        元件（例如對話框、捲軸區域）會維持系統配色而與 App 主題不一致。

        注意：`setThemeColor` 也會觸發全量 QSS 刷新，只在 accent 真的改變時呼叫；
        否則每次切換主題會刷新兩次，造成閃爍與中間態錯色。
        """
        from PySide6.QtGui import QColor

        from qfluentwidgets import isDarkTheme

        mapping = {THEME_DARK: Theme.DARK, THEME_LIGHT: Theme.LIGHT, THEME_SYSTEM: Theme.AUTO}
        setTheme(mapping.get(self.cfg.theme, Theme.DARK))
        if getattr(self, "_last_accent", None) != THEME_ACCENT:
            setThemeColor(THEME_ACCENT)
            self._last_accent = THEME_ACCENT
        sync_qt_color_scheme()
        # Mica 底色：Mica 開啟時視窗底為全透明，靠系統 DWM 材質著色；
        # 在無 DWM 的環境（offscreen／舊版 Windows）會透出黑色。
        # 注意不可用 setBackgroundColor()：它會啟動 120ms 動畫，
        # 而 qconfig.themeChanged 觸發的 _updateBackgroundColor 會把它蓋回透明。
        # 正確做法是覆寫 _normalBackgroundColor，讓框架自己的更新流程使用主題底色。
        try:
            from qfluentwidgets import isDarkTheme as _is_dark

            _dark_bg = QColor("#202020")
            _light_bg = QColor("#f9f9f9")
            self._darkBackgroundColor = _dark_bg
            self._lightBackgroundColor = _light_bg
            # pylint: disable=protected-access
            self._normalBackgroundColor = (  # type: ignore[method-assign]
                lambda _self=self: _dark_bg if _is_dark() else _light_bg
            )
            self.backgroundColorAni.stop()
            self.bgColorObject.backgroundColor = _dark_bg if _is_dark() else _light_bg
            self.update()
        except Exception:
            pass
        # 重新套用內容區背景色（頁面背景需跟隨主題）
        refresh_page_backgrounds(self)
        # 同步內容容器調色盤：viewport 會忽略 Fluent QSS，
        # 真正底色是容器 QWidget 的 Window 色彩角色（實測證實）
        sync_page_palettes(self)
        for page in (self.homePage, self.accountPage, self.logPage, self.settingsPage):
            page.update()

    # --- 資料刷新 ------------------------------------------------------
    def refresh_all(self) -> None:
        self.refresh_accounts()
        self.refresh_summary()
        rows = list(self._results.values()) or [
            self._account_row(a) for a in self.worker.accounts.accounts
        ]
        self.homePage.update_results(rows)
        try:
            self.homePage.set_drift_warning(bool(self.worker.engine.drift_accounts()))
        except Exception:
            pass

    def refresh_accounts(self) -> None:
        self.accountPage.update_accounts(
            [self._account_row(a) for a in self.worker.accounts.accounts]
        )

    def refresh_summary(self, next_run_text: str | None = None) -> None:
        if next_run_text is None:
            try:
                next_run_text = self.worker.scheduler.next_run_text()
            except Exception:
                next_run_text = ""
        self.homePage.update_summary(
            self.worker.accounts.summary(), next_run_text, self.worker.scheduler.running
        )

    @staticmethod
    def _account_row(account) -> dict:
        from app.constants import run_status_text

        status = account.last_status or ("success" if account.signed_in_today else "idle")
        try:
            status_text = run_status_text(RunStatus(status))
        except ValueError:
            status, status_text = "idle", t("status.todo")
        if not account.enabled:
            status, status_text = "idle", t("status.disabled")
        elif account.signed_in_today and not account.last_status:
            status_text = t("status.signed")
        user_part = account.user_id or t("status.not_logged")
        login_part = account.last_login_at or "-"
        return {
            "id": account.id,
            "account_id": account.id,
            "alias": account.display_name,
            "name": account.display_name,
            "sub": f"{t('status.id_prefix', id=user_part)}｜{t('status.last_login', time=login_part)}",
            "status": status,
            "status_text": status_text,
            "message": account.last_message or t("status.never_run"),
            "points": account.last_points,
            "time": account.last_run_at,
            "enabled": account.enabled,
        }