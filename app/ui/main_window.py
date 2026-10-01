"""主視窗：Fluent 介面（左側導覽 + 卡片式內容 + 標題列搜尋），風格參考 Ghost Downloader。"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from qfluentwidgets import (
    Action,
    FluentIcon as FIF,
    FluentWindow,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    MessageBox,
    NavigationItemPosition,
    StateToolTip,
    SystemTrayMenu,
    Theme,
    setTheme,
    setThemeColor,
)

from app import paths
from app.config import THEME_DARK, THEME_LIGHT, THEME_SYSTEM, AppConfig
from app.constants import APP_NAME, RUN_STATUS_TEXT, RunStatus
from app.core import autostart
from app.logger import logger
from app.ui.account_page import AccountPage
from app.ui.components import refresh_page_backgrounds, sync_qt_color_scheme
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
        self._results: dict[str, dict] = {}

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(*self._preferred_size())
        # 視窗不可被縮到無法使用（否則內容會被裁切、導覽列被收合）
        self.setMinimumSize(940, 620)
        # 不使用 Mica 半透明材質：它會跟隨 Windows 系統配色，
        # 造成 App 主題（淺色）與內容區底色不一致，且在深色主題下反而透出淗色底。
        try:
            self.setMicaEffectEnabled(False)
        except Exception:
            pass

        self.homePage = HomePage(self)
        self.accountPage = AccountPage(self)
        self.logPage = LogPage(self)
        self.settingsPage = SettingsPage(cfg, self._on_setting_changed, self)

        self._init_navigation()
        self._init_title_bar()
        self._init_tray()
        self._connect_signals()
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
        self.addSubInterface(self.homePage, FIF.HOME, "總覽")
        self.addSubInterface(self.accountPage, FIF.PEOPLE, "帳號")
        self.addSubInterface(self.logPage, FIF.DOCUMENT, "紀錄")
        self.addSubInterface(self.settingsPage, FIF.SETTING, "設定")
        try:
            self.navigationInterface.setExpandWidth(210)
            self.navigationInterface.expand(useAni=False)
        except Exception as exc:  # pragma: no cover
            logger.debug(f"展開導覽列失敗：{exc}")
        try:
            self.navigationInterface.addItem(
                routeKey="runNow",
                icon=FIF.PLAY,
                text="立即簽到",
                onClick=self.run_now,
                position=NavigationItemPosition.BOTTOM,
                tooltip="立即執行一次簽到",
            )
        except Exception as exc:  # pragma: no cover
            logger.debug(f"導覽列項目建立失敗：{exc}")

    def _init_title_bar(self) -> None:
        """在標題列加入「搜尋設定」框（Ghost Downloader 的招牌元素）。"""
        self.searchEdit = LineEdit(self.titleBar)
        self.searchEdit.setPlaceholderText("搜尋設定")
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
        self.trayIcon.setToolTip(f"{APP_NAME}｜每日自動簽到")
        self.trayMenu = SystemTrayMenu(parent=self)
        self.trayMenu.addAction(Action(FIF.PLAY, "立即簽到", triggered=self.run_now, parent=self))
        self.trayMenu.addAction(
            Action(FIF.HOME, "顯示主視窗", triggered=self.show_window, parent=self)
        )
        self.trayMenu.addAction(
            Action(FIF.HISTORY, "今日結果", triggered=self.show_results, parent=self)
        )
        self.trayMenu.addAction(
            Action(FIF.FOLDER, "開啟資料目錄", triggered=self.open_data_dir, parent=self)
        )
        self.trayMenu.addSeparator()
        self.trayMenu.addAction(Action(FIF.CLOSE, "結束", triggered=self.quit_app, parent=self))
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
                    "應用可能已過期",
                    "連續多次找不到簽到介面，建議按「重新掃描頁面」更新選擇器。",
                    ok=False,
                )
        elif event == "login_state":
            self._on_login_state(payload)
        elif event == "accounts_changed":
            self.refresh_all()
        elif event == "probe_finished":
            self.info_bar(
                "掃描完成",
                f"面板存在：{payload.get('panel')}｜候選元素：{payload.get('candidates')}｜"
                f"命中：{payload.get('matched') or '無'}",
                ok=True,
            )
        elif event == "browser_download":
            state = str(payload.get("state", ""))
            if state == "started":
                self.info_bar(
                    "正在下載瀏覽器核心", "約 150MB，請保持網路連線（可繼續使用其他功能）", ok=True,
                    duration=8000,
                )
            elif state == "finished":
                self.info_bar("瀏覽器核心就緒", str(payload.get("message", "")), ok=True)
            else:
                self.info_bar("下載失敗", str(payload.get("message", "")), ok=False, duration=10000)
        elif event == "error":
            message = str(payload.get("message", ""))
            logger.warning(message)
            self.info_bar("發生錯誤", message, ok=False)

    def _on_login_state(self, payload: dict) -> None:
        """登入流程各階段的提示（含開啟中的轉圈圈指示）。"""
        state = str(payload.get("state", ""))
        message = str(payload.get("message", ""))
        account_id = str(payload.get("account_id", ""))

        if state in ("launching", "opening", "waiting_run", "fitting"):
            self._show_login_progress(message or "正在開啟登入視窗…")
            self.accountPage.set_busy(account_id, True)
        elif state == "ready":
            self._show_login_progress("登入頁面已就緒，請在瀏覽器視窗完成登入", done=True)
            self.info_bar(
                "請完成登入",
                "已為您開啟 MiniMax 登入頁面，請選擇 Google／Email 驗證碼／GitHub 完成登入。",
                ok=True,
                duration=10000,
            )
        elif state == "success":
            self._show_login_progress("登入成功", done=True)
            self.accountPage.set_busy(account_id, False)
            self.info_bar("登入成功", f"{payload.get('user_name', '')} 的登入狀態已儲存", ok=True)
            self.notify("登入成功", f"{payload.get('user_name', '')} 已完成登入")
            self.refresh_all()
        elif state == "failed":
            self._show_login_progress(message or "登入未完成", done=True, failed=True)
            self.accountPage.set_busy(account_id, False)
            error_kind = str(payload.get("error", ""))
            title = {
                "network": "無法連線",
                "proxy": "代理伺服器問題",
                "ssl": "憑證錯誤",
                "blocked": "連線被阻擋",
                "timeout": "登入逾時",
                "closed": "視窗已關閉",
                "cancelled": "已取消登入",
                "no_browser": "找不到瀏覽器",
            }.get(error_kind, "登入未完成")
            self.info_bar(title, message, ok=False, duration=12000)
            if error_kind not in ("cancelled",):
                self.notify(title, message, ok=False)

        if account_id:
            self.refresh_accounts()

    def _show_login_progress(self, content: str, done: bool = False, failed: bool = False) -> None:
        """顯示（或更新）開啟登入視窗的進度提示；`done=True` 時收合。

        未完成時透過 StateToolTip 顯示轉圈圈，讓使用者知道程式正在動作。
        """
        tip = getattr(self, "_login_tip", None)
        if tip is None:
            tip = StateToolTip("開啟登入視窗", content, self)
            self._login_tip = tip
            tip.move(tip.getSuitablePos())
            tip.show()
            return
        tip.setContent(content)
        if done:
            tip.setState(True)
            tip.setContent(content + ("（失敗）" if failed else "（完成）"))
            self._login_tip = None
            QTimer.singleShot(4000, tip.close)
        else:
            tip.show()
            tip.move(tip.getSuitablePos())

    def _notify_result(self, payload: dict) -> None:
        status = str(payload.get("status", ""))
        alias = str(payload.get("alias", ""))
        if status == "success" and self.cfg.notify_success:
            self.notify("簽到成功", f"{alias} 獲得 {payload.get('points', 0)} 點")
        elif status in ("failed", "rate_limited", "drift") and self.cfg.notify_failure:
            self.notify("簽到失敗", f"{alias}：{payload.get('message', '')}", ok=False)
        elif status == "need_relogin" and self.cfg.notify_relogin:
            self.notify("需要重新登入", f"{alias} 的登入狀態已失效", ok=False)

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
            self.info_bar("引擎啟動中", "自動化引擎尚未就緒，請稍候再試。", ok=False)
            return
        self.homePage.set_running(True)
        self._results.clear()
        self.worker.request_run("manual")

    def add_account(self) -> None:
        accounts = self.worker.accounts
        account = accounts.add(alias=f"帳號 {len(accounts.accounts)}")
        self.refresh_all()
        self.info_bar(
            "已新增帳號",
            "將開啟瀏覽器視窗，請在該視窗完成登入（Google／Email 驗證碼／GitHub）。",
            duration=8000,
        )
        self.worker.request_login(account.id)

    def delete_account(self, account_id: str) -> None:
        account = self.worker.accounts.get(account_id)
        if account is None:
            return
        box = MessageBox(
            "確定要刪除此帳號？",
            f"「{account.display_name}」的登入 session 會被清除，之後需要重新登入。",
            self,
        )
        box.yesButton.setText("刪除")
        box.cancelButton.setText("取消")
        if not box.exec():
            return
        self.worker.accounts.remove(account_id)
        self._results.pop(account_id, None)
        self.homePage.update_results(list(self._results.values()))
        self.refresh_all()
        self.info_bar("已刪除帳號", account.display_name)

    def set_account_enabled(self, account_id: str, enabled: bool) -> None:
        self.worker.accounts.update(account_id, enabled=bool(enabled))
        self.refresh_accounts()
        self.refresh_summary()
        logger.info(f"{'啟用' if enabled else '停用'}帳號：{account_id[:6]}")

    def show_window(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()

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
            if not self._tray_hint_shown:
                self._tray_hint_shown = True
                self.notify("仍在背景執行", "程式已縮到系統匣，會依排程自動簽到。")
        else:
            self.quit_app()

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
        elif key == "autostart":
            if not autostart.apply(bool(value)):
                self.info_bar("設定失敗", "無法寫入開機自啓動登錄檔（Windows 登錄檔權限問題）", ok=False)
        elif key == "daily_time":
            self.refresh_summary()
        logger.info(f"設定已更新：{key} = {value}")

    def _confirm_clear_sessions(self) -> None:
        box = MessageBox("確定要清除所有登入狀態？", "所有帳號都必須重新登入才能簽到。", self)
        box.yesButton.setText("清除")
        box.cancelButton.setText("取消")
        if not box.exec():
            self.settingsPage.reload(self.cfg)
            return
        manager = self.worker.accounts
        for account in manager.accounts:
            manager.clear_state(account)
            manager.update(account.id, persist=False, last_status="", last_message="尚未登入")
        manager.save()
        self._results.clear()
        self.refresh_all()
        self.info_bar("已清除登入狀態", "請重新登入各帳號")

    def _confirm_clear_local_data(self) -> None:
        """清除日誌與診斷檔（保留設定與帳號）。"""
        box = MessageBox(
            "確定要清除本機資料？",
            f"將刪除下列內容（不含設定與帳號）：\n{paths.logs_dir()}\n{paths.diagnostics_dir()}",
            self,
        )
        box.yesButton.setText("清除")
        box.cancelButton.setText("取消")
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
        self.info_bar("已清除本機資料", f"共移除 {removed} 個項目")
        logger.info(f"已清除本機資料：{removed} 個項目")

    def _apply_theme(self) -> None:
        """套用介面主題。

        除了 qfluentwidgets 的 `setTheme`，還必須同步 Qt 的 colorScheme：
        Qt 6.8+ 會自動跟隨 Windows 的深色模式，若不覆寫，使用原生調色盤繪製的
        元件（例如對話框、捲軸區域）會維持系統配色而與 App 主題不一致。
        """
        mapping = {THEME_DARK: Theme.DARK, THEME_LIGHT: Theme.LIGHT, THEME_SYSTEM: Theme.AUTO}
        setTheme(mapping.get(self.cfg.theme, Theme.DARK))
        setThemeColor(THEME_ACCENT)
        sync_qt_color_scheme()
        # 重新套用內容區背景色（頁面背景需跟隨主題）
        refresh_page_backgrounds(self)
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
        status = account.last_status or ("success" if account.signed_in_today else "idle")
        try:
            status_text = RUN_STATUS_TEXT.get(RunStatus(status), "待簽到")
        except ValueError:
            status, status_text = "idle", "待簽到"
        if not account.enabled:
            status, status_text = "idle", "已停用"
        elif account.signed_in_today and not account.last_status:
            status_text = "今日已簽到"
        return {
            "id": account.id,
            "account_id": account.id,
            "alias": account.display_name,
            "name": account.display_name,
            "sub": f"ID {account.user_id or '尚未登入'}｜最後登入 {account.last_login_at or '-'}",
            "status": status,
            "status_text": status_text,
            "message": account.last_message or "尚未執行",
            "points": account.last_points,
            "time": account.last_run_at,
            "enabled": account.enabled,
        }