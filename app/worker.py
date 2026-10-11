"""背景自動化執行緒：在專用 asyncio 事件迴圈中執行 Playwright 與排程器。

GUI（Qt 主執行緒）與自動化（此執行緒）只透過 Qt Signal 溝通，因此介面不會被阻塞。
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, Coroutine

from PySide6.QtCore import QThread, Signal

from app import paths
from app.config import AppConfig
from app.constants import BASE_URL
from app.core import diagnostics, selectors
from app.core.account import AccountManager
from app.core.browser import BrowserManager, builtin_browser_available, setup_browsers_path, system_browsers
from app.core.engine import CheckinEngine
from app.core.scheduler import Scheduler
from app.core.state import RunStateStore
from app.i18n import t
from app.logger import logger


class AutomationWorker(QThread):
    """負責所有自動化工作（簽到、登入擷取、排程）。"""

    logMessage = Signal(str, str)        # level, text
    eventReceived = Signal(str, dict)    # event 名稱, payload

    def __init__(self, cfg: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.cfg = cfg
        self.accounts = AccountManager(encrypt=cfg.encrypt_sessions)
        self.state = RunStateStore()
        self.browser = BrowserManager(self.accounts)
        self.engine = CheckinEngine(cfg, self.accounts, self.browser, self.state, emit=self._emit)
        self.scheduler = Scheduler(cfg, self.engine, self.accounts, self.state, emit=self._emit)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._shutdown = asyncio.Event()
        self._ready = False
        self._login_cancel: asyncio.Event | None = None
        self._login_busy = False

    @property
    def ready(self) -> bool:
        return self._ready

    # --- 供 GUI 呼叫（執行緒安全） ------------------------------------
    def run(self) -> None:  # QThread 進入點
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._main())
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()
            self._loop = None

    def _submit(self, coro: Coroutine[Any, Any, Any], what: str) -> None:
        if self._loop is None or not self._loop.is_running():
            self._emit("error", {"message": t("worker.engine_not_ready", what=what)})
            try:
                coro.close()
            except Exception:
                pass
            return
        asyncio.run_coroutine_threadsafe(coro, self._loop)

    def request_run(self, reason: str = "manual", only_ids: list[str] | None = None) -> None:
        self._submit(self.scheduler.trigger(reason, only_ids), t("worker.action.run"))

    def request_login(self, account_id: str) -> None:
        self._submit(self._capture_login(account_id), t("worker.action.login"))

    def request_cancel(self) -> None:
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self.scheduler.cancel_current)

    def request_shutdown(self) -> None:
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._shutdown.set)

    def request_cancel_login(self) -> None:
        """取消正在等待的登入（使用者不想繼續時）。"""
        if self._login_cancel is not None:
            self._login_cancel.set()

    def request_probe(self, account_id: str | None = None) -> None:
        self._submit(self._probe(account_id), t("worker.action.probe"))

    def request_download_browser(self) -> None:
        self._submit(self._download_browser(), t("worker.action.download"))

    def request_check_update(self, manual: bool = False) -> None:
        """檢查應用更新（manual=True 時忽略每天一次限制）。"""
        self._submit(self._check_update(manual), t("worker.action.check_update"))

    # --- 內部 ----------------------------------------------------------
    def _emit(self, event: str, payload: dict[str, Any]) -> None:
        self.eventReceived.emit(event, payload)

    async def _main(self) -> None:
        self._shutdown = asyncio.Event()
        self._emit("starting", {})
        # 不在啟動時就開啟瀏覽器：改用「需要時才啟動」，
        # 這樣按下「新增帳號／重新登入」時只需啟動一次顯示視窗，開啟速度大幅提升。
        try:
            setup_browsers_path()
            if not builtin_browser_available() and not system_browsers():
                self._emit(
                    "error",
                    {
                        "message": t("worker.nobrowser"),
                    },
                )
                return
            self.scheduler.start()
        except Exception as exc:
            logger.exception("自動化引擎啟動失敗")
            self._emit("error", {"message": t("worker.engine_fail", detail=exc)})
            return
        self._ready = True
        self._emit("ready", {"next_run_text": self.scheduler.next_run_text()})
        # 啟動後檢查一次應用更新（每天最多一次，失敗靜默）
        if self.cfg.check_update_on_start:
            try:
                await self._check_update(manual=False)
            except Exception:
                pass
        try:
            await self._shutdown.wait()
        finally:
            self._ready = False
            await self.scheduler.stop()
            await self.browser.stop()
            logger.info("自動化引擎已停止")
            self._emit("stopped", {})

    async def _capture_login(self, account_id: str) -> None:
        account = self.accounts.get(account_id)
        if account is None:
            self._emit("error", {"message": t("login.account.missing")})
            return

        if self._login_busy:
            self._emit(
                "login_state",
                {
                    "account_id": account_id,
                    "state": "failed",
                    "message": t("login.state.busy"),
                },
            )
            return

        # 等待進行中的簽到結束，避免與互動登入搶同一個瀏覽器
        waited = 0.0
        while self.scheduler.running and waited < 300:
            self._emit(
                "login_state",
                {
                    "account_id": account_id,
                    "state": "waiting_run",
                    "message": t("login.state.waiting"),
                },
            )
            await asyncio.sleep(1.0)
            waited += 1

        self._login_busy = True
        self._login_cancel = asyncio.Event()

        def on_stage(stage: str, message: str) -> None:
            self._emit(
                "login_state",
                {"account_id": account_id, "state": stage, "message": message},
            )

        try:
            result = await self.browser.capture_login(
                account,
                self.cfg,
                on_stage=on_stage,
                cancel=self._login_cancel,
            )
        except Exception as exc:  # pragma: no cover - 保底
            logger.exception("登入流程錯誤")
            self._emit(
                "login_state",
                {"account_id": account_id, "state": "failed", "message": t("login.state.fail", detail=exc)},
            )
            return
        finally:
            self._login_busy = False

        if not result.ok or not result.state:
            logger.warning(f"登入未完成（{result.error}）：{result.message}")
            self._emit(
                "login_state",
                {
                    "account_id": account_id,
                    "state": "failed",
                    "error": result.error,
                    "message": result.message or t("login.state.unfinished"),
                },
            )
            return

        info = result.info or {}
        account.user_name = info.get("user_name") or account.user_name
        account.user_id = info.get("user_id") or account.user_id
        account.avatar = info.get("avatar") or account.avatar
        account.last_status = ""
        account.last_message = t("login.state.signed")
        account.drift_count = 0
        self.accounts.save_state(account, result.state)
        self.accounts.update(account.id, persist=True)
        self._emit(
            "login_state",
            {
                "account_id": account_id,
                "state": "success",
                "user_name": account.display_name,
                "message": t("login.state.saved"),
            },
        )
        self._emit("accounts_changed", {})

    async def _probe(self, account_id: str | None = None) -> None:
        """以顯示視窗開啟 MiniMax 頁面，掃描簽到元素並輸出診斷檔（官方改版時使用）。"""
        account = (
            self.accounts.get(account_id) if account_id else next(iter(self.accounts.accounts), None)
        )
        if account is None:
            self._emit("error", {"message": t("login.account.no_account")})
            return
        if not self.accounts.has_state(account):
            self._emit("error", {"message": t("login.account.not_logged")})
            return
        logger.info(f"開始掃描 MiniMax 頁面（{account.display_name}）…")
        folder = diagnostics.session_dir(f"{account.display_name}_probe")
        context = None
        try:
            await asyncio.sleep(0.1)
            context = await self.browser.new_context(account, self.cfg)
            page = await context.new_page()
            await page.goto(
                BASE_URL,
                wait_until="domcontentloaded",
                timeout=max(30, self.cfg.timeout_seconds) * 1000,
            )
            await asyncio.sleep(3)
            scan = await selectors.heuristic_scan(page)
            diagnostics.write_json(folder, "probe_scan.json", scan)
            await diagnostics.capture_page(page, folder, "probe")
            match = await selectors.find_claim_button(page)
            self._emit(
                "probe_finished",
                {
                    "folder": str(folder),
                    "panel": scan.get("panel_present"),
                    "fingerprint": scan.get("fingerprint"),
                    "candidates": len(scan.get("claim_candidates") or []),
                    "matched": match.selector if match else "",
                },
            )
        except Exception as exc:
            logger.warning(f"掃描失敗：{exc}")
            self._emit("error", {"message": t("worker.probe_fail", detail=exc)})
        finally:
            if context is not None:
                try:
                    await context.close()
                except Exception:
                    pass

    async def _check_update(self, manual: bool = False) -> None:
        """檢查應用更新：每天最多自動查一次，手動可隨時查。"""
        from app.constants import APP_VERSION
        from app.core import updater

        today = updater.today_text()
        if not manual and self.cfg.last_update_check == today:
            return  # 今天已查過（成功或失敗都算，避免反覆打 API）
        info = await asyncio.to_thread(updater.fetch_latest)
        self.cfg.last_update_check = today
        try:
            self.cfg.save()
        except Exception:
            pass
        if not info.checked:
            return
        if info.error:
            logger.debug(f"更新檢查失敗：{info.error}")
            return
        if info.has_update:
            logger.info(f"發現新版本：{info.latest}（目前 {APP_VERSION}）")
            self._emit(
                "update_available",
                {"latest": info.latest, "current": APP_VERSION, "url": info.url},
            )
        elif manual:
            self._emit(
                "update_checked",
                {"latest": info.latest or APP_VERSION, "current": APP_VERSION, "url": info.url},
            )

    async def _download_browser(self) -> None:
        """下載內建 Chromium 核心到本機資料目錄（精簡版安裝使用）。

        使用 Playwright 自帶的驅動程式，不需額外工具；完成後會重啟瀏覽器以套用新核心。
        """
        if builtin_browser_available():
            self._emit("browser_download", {"state": "finished", "message": t("browser.download.exists")})
            return
        target = paths.browsers_dir()
        self._emit("browser_download", {"state": "started", "path": str(target)})
        logger.info(f"開始下載瀏覽器核心（約 150MB）到 {target} …")
        try:
            from playwright._impl._driver import compute_driver_executable

            driver = compute_driver_executable()
            if isinstance(driver, (tuple, list)):
                node, cli = driver[0], driver[1]
            else:  # 新版回傳單一可執行檔路徑
                node, cli = None, driver
            if node:
                command = [str(node), str(cli), "install", "chromium"]
            elif str(cli).lower().endswith(".py"):
                command = [sys.executable, str(cli), "install", "chromium"]
            else:
                command = [str(cli), "install", "chromium"]

            env = os.environ.copy()
            env["PLAYWRIGHT_BROWSERS_PATH"] = str(target)
            kwargs: dict[str, Any] = {
                "env": env,
                "stdout": asyncio.subprocess.PIPE,
                "stderr": asyncio.subprocess.STDOUT,
            }
            if sys.platform == "win32":
                # 打包版 console=False 下子行程仍可能閃出黑窗，強制隱藏。
                kwargs["creationflags"] = getattr(
                    asyncio.subprocess, "CREATE_NO_WINDOW", 0x08000000
                )
            process = await asyncio.create_subprocess_exec(
                *command,
                **kwargs,
            )
            assert process.stdout is not None
            while True:
                raw = await process.stdout.readline()
                if not raw:
                    break
                text = raw.decode("utf-8", "ignore").strip()
                if text:
                    logger.debug(f"[playwright] {text}")
            code = await process.wait()
        except Exception as exc:
            logger.exception("下載瀏覽器核心失敗")
            self._emit(
                "browser_download",
                {
                    "state": "failed",
                    "message": t("browser.download.fail", detail=exc),
                },
            )
            return

        if code == 0 and builtin_browser_available():
            logger.info("瀏覽器核心下載完成")
            try:
                await self.browser.stop()  # 讓下次啟動重新載入新的核心
            except Exception:
                pass
            self._emit(
                "browser_download",
                {"state": "finished", "message": t("browser.download.done")},
            )
        else:
            self._emit(
                "browser_download",
                {
                    "state": "failed",
                    "message": t("browser.download.incomplete", code=code),
                },
            )
