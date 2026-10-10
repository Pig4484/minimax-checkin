"""Playwright 瀏覽器管理：單一瀏覽器實例 + 每帳號獨立 context（cookie 隔離）。

瀏覽器來源優先順序（找不到就自動降級，並寫入日誌）：

1. **內建 Chromium**（`channel="chromium"`）：安裝檔附帶，或使用者於「設定」頁下載到 Local。
   使用「新版 headless」，因此不需要額外的 chromium_headless_shell。
2. **系統 Google Chrome**（`channel="chrome"`）
3. **系統 Microsoft Edge**（`channel="msedge"`，Windows 內建）

因此即使不安裝任何瀏覽器核心，只要有 Chrome 或 Edge 就能運作。
"""

from __future__ import annotations

import asyncio
import base64
import inspect
import json
import os
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from playwright.async_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Playwright,
    TimeoutError as PlaywrightTimeout,
    async_playwright,
)

from app import paths
from app.constants import (
    BASE_URL,
    LOGIN_HOST,
    LOGIN_STATE_SIGNED_IN,
    LOGIN_STATE_SIGNED_OUT,
    USER_AGENT,
)
from app.core.account import Account, AccountManager
from app.i18n import t
from app.logger import logger

LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-default-browser-check",
    "--no-first-run",
    "--disable-infobars",
]

# 顯示視窗模式（互動登入用）：固定尺寸、由程式置中，而非最大化。
# 背景：--start-maximized 在多螢幕／DPI 縮放／無主控台行程啟動時可能失效，
# 且固定 viewport=1440x900 會撐大視窗、底部被工作列切掉（見 tools/repro_login_window.py）。
# 因此改用 --window-size 固定初始尺寸＋ CDP 置中（_center_login_window），
# 再以 _fit_page_to_window 縮放兜底。1100x720 在 CSS 工作區（1280x752）與
# 實體解析度（1920x1200）下都塞得下，無論 CDP 用哪種像素單位都不會溢出。
LOGIN_WINDOW_WIDTH = 1100
LOGIN_WINDOW_HEIGHT = 720
# 登入視窗的頁面 viewport：外框 1100x720 扣掉標題列＋網址列＋邊框（約 120px），
# 剩下約 600px 可見高度；寬度扣邊框約 16px。固定 viewport 讓版面可預測，
# 溢出部分由 _fit_page_to_window 縮放兜底（而非依賴視窗最大化）。
LOGIN_VIEWPORT = {"width": 1080, "height": 600}
HEADED_LAUNCH_ARGS = [
    *LAUNCH_ARGS,
    f"--window-size={LOGIN_WINDOW_WIDTH},{LOGIN_WINDOW_HEIGHT}",
]

VIEWPORT = {"width": 1440, "height": 900}

# 互動登入的等待上限（秒）。過長會讓使用者關掉視窗後仍卡住後續操作。
LOGIN_TIMEOUT_SECONDS = 300

# 登入頁自動縮放的下限（避免縮得太小導致無法閱讀／點擊）
MIN_ZOOM = 0.65

CHANNEL_LABELS = {
    "chromium": "browser.channel.chromium",
    "chrome": "browser.channel.chrome",
    "msedge": "browser.channel.msedge",
}
_CHANNEL_ORDER = ("chromium", "chrome", "msedge")


def channel_label(name: str) -> str:
    """瀏覽器通道顯示名稱（執行時查表，跟隨目前語言）。"""
    key = CHANNEL_LABELS.get(name)
    return t(key) if key else name


class BrowserLaunchError(RuntimeError):
    """所有候選瀏覽器都無法啟動時拋出。"""


@dataclass
class LoginResult:
    """互動登入的結果。"""

    ok: bool = False
    state: dict[str, Any] | None = None
    info: dict[str, Any] = field(default_factory=dict)
    error: str = ""      # network / timeout / blocked / closed / cancelled / no_browser / unknown
    message: str = ""


def classify_navigation_error(exc: Exception) -> tuple[str, str]:
    """把 Playwright 的網路錯誤轉成使用者看得懂的說明。"""
    text = str(exc)
    lowered = text.lower()
    first_line = text.splitlines()[0][:140] if text else ""

    network_codes = (
        "err_name_not_resolved",
        "err_internet_disconnected",
        "err_connection_refused",
        "err_connection_reset",
        "err_connection_closed",
        "err_network_changed",
        "err_address_unreachable",
        "err_name_resolution_failed",
    )
    if any(code in lowered for code in network_codes):
        return "network", t("login.net.network")
    if "err_proxy" in lowered or "proxy" in lowered:
        return "proxy", t("login.net.proxy")
    if "err_ssl" in lowered or "certificate" in lowered or "tls" in lowered:
        return "ssl", t("login.net.ssl")
    if "err_timed_out" in lowered or "timeout" in lowered:
        return "timeout", t("login.net.timeout")
    if "err_aborted" in lowered or "err_blocked" in lowered:
        return "blocked", t("login.net.blocked")
    return "unknown", t("login.net.unknown", detail=first_line or t("login.net.unknown_detail"))


def quick_reachability_check(host: str = "agent.minimax.io", timeout: float = 6.0) -> tuple[bool, str]:
    """快速的網路連線預檢（不啟動瀏覽器），提早告訴使用者「連不上」。"""
    try:
        socket.create_connection((host, 443), timeout=timeout).close()
        return True, ""
    except socket.gaierror:
        return False, t("login.net.dns")
    except (TimeoutError, socket.timeout):
        return False, t("login.net.timeout2")
    except OSError as exc:
        return False, t("login.net.failed", detail=exc)


def _default_browsers_dir() -> Path | None:
    """Playwright 預設的瀏覽器目錄（未設定 PLAYWRIGHT_BROWSERS_PATH 時使用）。"""
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    return Path(local) / "ms-playwright"


def _browser_dirs() -> list[Path]:
    """回傳可能包含瀏覽器核心的目錄，優先順序：內建 → 使用者下載 → Playwright 預設。"""
    candidates: list[Path] = [paths.bundled_browsers_dir(), paths.local_dir() / "browsers"]
    default_dir = _default_browsers_dir()
    if default_dir is not None:
        candidates.append(default_dir)
    return [d for d in candidates if d.is_dir()]


def _has_chromium(directory: Path) -> bool:
    try:
        return any(
            item.is_dir() and item.name.startswith("chromium-") and not item.name.startswith("chromium_headless")
            for item in directory.iterdir()
        )
    except OSError:
        return False


def builtin_browser_available() -> bool:
    """內建（或已下載）的 Chromium 是否可用。"""
    return any(_has_chromium(directory) for directory in _browser_dirs())


def setup_browsers_path() -> Path | None:
    """讓 Playwright 指向內建或已下載的瀏覽器目錄。

    必須在 ``async_playwright().start()`` 之前呼叫；使用者若自行設定環境變數則尊重其設定。
    """
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        return Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"])
    for directory in _browser_dirs():
        if _has_chromium(directory):
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(directory)
            return directory
    return None


def system_browsers() -> list[str]:
    """偵測系統已安裝的 Chrome / Edge。"""
    candidates = {
        "chrome": (
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ),
        "msedge": (
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ),
    }
    found = [
        name
        for name, exe_paths in candidates.items()
        if any(Path(path).exists() for path in exe_paths)
    ]
    return found


def browser_status() -> dict[str, Any]:
    """給 GUI 顯示的瀏覽器狀態摘要。"""
    return {
        "builtin": builtin_browser_available(),
        "system": system_browsers(),
        "path": os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""),
    }


async def _measure_fit_page(page) -> dict[str, int]:
    """量測頁面是否溢出：回傳可見高度與最底部位置。

    優先以「實際元素」的邊界計算；找不到元素時改用 **body 的
    getBoundingClientRect().bottom**（會正確反映 CSS zoom，而 scrollHeight 不會）。
    """
    return await page.evaluate(
        """() => {
            const rect = (el) => {
                const r = el.getBoundingClientRect();
                return r.width > 1 && r.height > 1 ? r.bottom : 0;
            };
            let bottom = 0;
            for (const el of document.querySelectorAll(
                'button, a, input, p, span, div, h1, h2')) {
                const b = rect(el);
                if (b > bottom) bottom = b;
            }
            if (bottom <= 0) {
                bottom = document.body ? document.body.getBoundingClientRect().bottom : 0;
            }
            return { innerH: window.innerHeight, bottomMost: Math.ceil(bottom) };
        }"""
    )


class BrowserManager:
    """管理 Playwright 與瀏覽器生命週期。

    設計：**只啟動一個瀏覽器行程**，每個帳號用 `new_context()` 取得獨立 cookie 艙，
    因此多帳號登入狀態互不干擾，也不必開多個瀏覽器。
    """

    def __init__(self, accounts: AccountManager) -> None:
        self.accounts = accounts
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._headless = True
        self._channel = "chromium"          # 實際使用的瀏覽器
        self._requested_channel = "chromium"  # 使用者設定的偏好
        self._proxy = ""
        # 避免「互動登入」與「自動簽到」同時操作瀏覽器（模式不同會導致重啟）
        self.gate = asyncio.Lock()
        # 長期操作互斥：整輪簽到 或 互動登入 一次只能有一個進行中，
        # 否則 headed(登入) 與 headless(簽到) 會互相把瀏覽器重啟、打斷對方。
        self.operation = asyncio.Lock()

    @property
    def running(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    @property
    def headless(self) -> bool:
        return self._headless

    @property
    def active_browser(self) -> str:
        """目前實際使用的瀏覽器（可能因降級而與設定不同）。"""
        return self._channel

    async def start(self, headless: bool = True, channel: str = "chromium", proxy: str = "") -> None:
        setup_browsers_path()  # 必須在啟動 Playwright 之前設定
        if self._playwright is None:
            self._playwright = await async_playwright().start()
        await self._launch(headless, channel, proxy)

    async def _launch(self, headless: bool, channel: str, proxy: str) -> None:
        """啟動瀏覽器；失敗時依序改用其他可用核心（內建 → Chrome → Edge）。"""
        await self._close_browser()
        assert self._playwright is not None
        setup_browsers_path()

        order = [channel] + [name for name in _CHANNEL_ORDER if name != channel]
        failures: list[str] = []
        for candidate in order:
            if candidate == "chromium" and not builtin_browser_available():
                failures.append(t("browser.launch.tried_detail", label=channel_label("chromium"), reason=t("browser.launch.no_core")))
                continue
            if candidate in ("chrome", "msedge") and candidate not in system_browsers():
                failures.append(t("browser.launch.tried_detail", label=channel_label(candidate), reason=t("browser.launch.no_system")))
                continue
            kwargs: dict[str, Any] = {
                "headless": headless,
                "args": LAUNCH_ARGS if headless else HEADED_LAUNCH_ARGS,
                "ignore_default_args": ["--enable-automation"],
                # 明確指定 channel：使用「內建完整 Chromium + 新版 headless」，
                # 因此不需要額外下載 chromium_headless_shell
                "channel": candidate,
            }
            if proxy:
                kwargs["proxy"] = {"server": proxy}
            try:
                self._browser = await self._playwright.chromium.launch(**kwargs)
            except PlaywrightError as exc:
                failures.append(t("browser.launch.tried_detail", label=channel_label(candidate), reason=str(exc).splitlines()[0][:120]))
                continue
            self._headless, self._channel, self._proxy = headless, candidate, proxy
            self._requested_channel = channel
            if candidate != channel:
                logger.warning(
                    f"設定的 {CHANNEL_LABELS.get(channel, channel)} 無法使用，"
                    f"已自動改用 {CHANNEL_LABELS[candidate]}"
                )
            logger.info(
                f"瀏覽器已啟動（{channel_label(candidate)}／{'無頭' if headless else '顯示視窗'}）"
            )
            return
        raise BrowserLaunchError(t("browser.launch.fail", tried="；".join(failures) or t("browser.launch.no_browser")))

    async def ensure(self, headless: bool, channel: str = "chromium", proxy: str = "") -> None:
        """確保瀏覽器以指定模式運行；模式不同時會自動重啟。"""
        if self._playwright is None:
            await self.start(headless, channel, proxy)
            return
        if (
            not self.running
            or self._headless != headless
            or self._requested_channel != channel
            or self._proxy != proxy
        ):
            await self._launch(headless, channel, proxy)

    async def _close_browser(self) -> None:
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None

    async def stop(self) -> None:
        await self._close_browser()
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    # ------------------------------------------------------------------
    def _context_kwargs(
        self, cfg, state: dict[str, Any] | None, headed: bool = False
    ) -> dict[str, Any]:
        """建立 context 的共用選項。

        方案 B（固定視窗置中）：登入視窗一律使用與視窗外框對齊的固定
        viewport（``LOGIN_VIEWPORT``），不再看全域 ``cfg.headless``。
        原因：capture_login() 用 headed 啟動瀏覽器，但以前看的是全域
        ``cfg.headless``（預設 True），导致登入拿到 1440x900、底部被
        工作列切掉。呼叫端必須明確傳入 headed=True（登入）或省略（簽到）。
        """
        kwargs: dict[str, Any] = {
            "storage_state": state or None,
            "user_agent": cfg.custom_user_agent or USER_AGENT,
            "locale": "zh-TW",
            "timezone_id": "Asia/Taipei",
        }
        if headed:
            kwargs["viewport"] = dict(LOGIN_VIEWPORT)
        elif cfg.headless:
            kwargs["viewport"] = VIEWPORT
        else:
            kwargs["no_viewport"] = True
        return kwargs

    async def new_context(self, account: Account, cfg) -> BrowserContext:
        """以帳號的 storage_state 建立隔離 context（與其他帳號 cookie 完全隔離）。"""
        async with self.gate:
            await self.ensure(cfg.headless, cfg.browser_channel, cfg.proxy)
            assert self._browser is not None
            state = self.accounts.load_state(account)
            context = await self._browser.new_context(**self._context_kwargs(cfg, state))
            context.set_default_timeout(cfg.timeout_seconds * 1000)
            return context

    async def update_state(self, account: Account, context: BrowserContext) -> None:
        """把 context 的最新 cookie/localStorage 寫回帳號（token 續期後保持有效）。"""
        try:
            state = await context.storage_state()
            self.accounts.save_state(account, state)
        except Exception as exc:  # pragma: no cover
            logger.warning(f"更新 session 失敗：{exc}")

    # ------------------------------------------------------------------
    @staticmethod
    async def _notify(on_stage: Callable[[str, str], Any] | None, stage: str, message: str) -> None:
        """回報登入階段（launching / opening / ready / …）供 GUI 顯示進度。"""
        if on_stage is None:
            return
        try:
            result = on_stage(stage, message)
            if inspect.isawaitable(result):
                await result
        except Exception:  # pragma: no cover - UI 例外不應影響登入
            pass

    async def _finish_login(self, context: BrowserContext, page) -> LoginResult:
        """登入成功：補齊使用者資訊並保存 session。"""
        await asyncio.sleep(2.0)  # 等頁面把 token / 使用者資訊寫入
        info = await self.read_user_info(page)
        try:
            state = await context.storage_state()
        except Exception as exc:
            return LoginResult(error="unknown", message=f"無法儲存登入狀態：{exc}")
        logger.info(f"登入成功：{info.get('user_name') or info.get('user_id')}")
        return LoginResult(ok=True, state=state, info=info)

    async def _enter_login_page(self, page) -> bool:
        """點擊官方的 Sign in，直接進入 MiniMax 登入頁；回傳是否已在登入頁。

        必須等按鈕真正渲染出來（`domcontentloaded` 時前端尚未 hydrate），
        並先移除會遮擋點擊的公告彈窗。
        """
        if LOGIN_HOST in page.url:
            return True

        try:
            await page.wait_for_selector(LOGIN_STATE_SIGNED_OUT, state="attached", timeout=25000)
        except PlaywrightTimeout:
            logger.debug("找不到登入按鈕（可能已登入或頁面未載入完成）")
            return False

        # 移除可能蓋住按鈕的彈窗／遮罩（不影響後續的登入請求）
        try:
            await page.evaluate(
                """() => {
                    document.querySelectorAll('[aria-modal="true"], div.bg-utility_overlay')
                        .forEach((el) => el.remove());
                }"""
            )
        except Exception:
            pass

        button = page.locator(LOGIN_STATE_SIGNED_OUT).first
        try:
            await button.click(timeout=8000)
        except PlaywrightError as exc:
            logger.debug(f"直接點擊登入按鈕失敗（改用派送事件）：{exc}")
            try:
                await button.dispatch_event("click")
            except PlaywrightError:
                return False

        try:
            await page.wait_for_url(f"**{LOGIN_HOST}/**", timeout=20000)
        except PlaywrightTimeout:
            return LOGIN_HOST in page.url
        return True

    async def _maximize_window(self, context, page) -> bool:
        """（歷史相容保留）確保瀏覽器視窗填滿螢幕工作區。

        方案 B 起登入流程已改用 :meth:`_center_login_window`（固定尺寸置中），
        不再依賴最大化。此方法僅保留給舊測試與可能的外部呼叫，行為不變。
        """
        try:
            session = await context.new_cdp_session(page)
        except Exception as exc:
            logger.debug(f"無法建立 CDP session：{exc}")
            return False

        for attempt in range(3):
            try:
                info = await session.send("Browser.getWindowForTarget")
                window_id = info.get("windowId")
                if not window_id:
                    return False
                before = (await session.send(
                    "Browser.getWindowBounds", {"windowId": window_id}
                )).get("bounds", {})
                bw = int(before.get("width") or 0)
                bh = int(before.get("height") or 0)

                if bw < 640 or bh < 480:
                    await session.send(
                        "Browser.setWindowBounds",
                        {"windowId": window_id, "bounds": {"windowState": "maximized"}},
                    )
                    await asyncio.sleep(0.4)
                else:
                    return True  # 尺寸已足夠大，視為已填滿

                after = (await session.send(
                    "Browser.getWindowBounds", {"windowId": window_id}
                )).get("bounds", {})
                state = after.get("windowState")
                aw, ah = int(after.get("width") or 0), int(after.get("height") or 0)
                logger.debug(
                    f"瀏覽器視窗：{bw}x{bh} → {aw}x{ah}（state={state}）"
                )
                if state == "maximized" or (aw >= bw and ah >= bh):
                    return True
            except Exception as exc:
                logger.debug(f"最大化視窗失敗（第 {attempt + 1} 次）：{exc}")
                await asyncio.sleep(0.3)
        return False
    async def _center_login_window(self, context, page) -> bool:
        """把登入視窗設為固定尺寸並置中（方案 B 核心，回傳是否成功）。

        為什麼不用最大化：--start-maximized 在多螢幕／DPI 縮放／無主控台
        行程啟動時可能失效，且最大化視窗仍可能被工作列蓋住底部。
        固定 1100x720＋置中可保證在 1280x752 工作區內完整可見；
        剩餘的頁面溢出由 _fit_page_to_window 縮放兜底。
        """
        try:
            session = await context.new_cdp_session(page)
        except Exception as exc:
            logger.debug(f"無法建立 CDP session：{exc}")
            return False
        for attempt in range(3):
            try:
                info = await session.send("Browser.getWindowForTarget")
                window_id = info.get("windowId")
                if not window_id:
                    return False
                before = (await session.send(
                    "Browser.getWindowBounds", {"windowId": window_id}
                )).get("bounds", {})
                bw = int(before.get("width") or 0)
                bh = int(before.get("height") or 0)
                # 置中座標：以主螢幕可用區（扣工作列）為基準，避免蓋住工作列。
                # Qt 取不到時退回 1280x752（本機實測值）。
                try:
                    from PySide6.QtWidgets import QApplication

                    app = QApplication.instance()
                    g = app.primaryScreen().availableGeometry() if app else None
                    if g is None:
                        from PySide6.QtGui import QGuiApplication

                        g = QGuiApplication.primaryScreen().availableGeometry()
                    avail_w, avail_h = g.width(), g.height()
                    origin_x, origin_y = g.x(), g.y()
                except Exception:
                    avail_w, avail_h, origin_x, origin_y = 1280, 752, 0, 0
                width = min(LOGIN_WINDOW_WIDTH, avail_w - 40)
                height = min(LOGIN_WINDOW_HEIGHT, avail_h - 40)
                left = origin_x + max(0, (avail_w - width) // 2)
                top = origin_y + max(0, (avail_h - height) // 2)
                if abs(bw - width) <= 8 and abs(bh - height) <= 8:
                    return True  # 已是目標尺寸（允許邊框誤差）
                await session.send(
                    "Browser.setWindowBounds",
                    {
                        "windowId": window_id,
                        "bounds": {
                            "left": left,
                            "top": top,
                            "width": width,
                            "height": height,
                            "windowState": "normal",
                        },
                    },
                )
                await asyncio.sleep(0.4)
                after = (await session.send(
                    "Browser.getWindowBounds", {"windowId": window_id}
                )).get("bounds", {})
                aw, ah = int(after.get("width") or 0), int(after.get("height") or 0)
                logger.debug(f"登入視窗置中：{bw}x{bh} → {aw}x{ah}（目標 {width}x{height}）")
                if abs(aw - width) <= 16 and abs(ah - height) <= 16:
                    return True
            except Exception as exc:
                logger.debug(f"置中登入視窗失敗（第 {attempt + 1} 次）：{exc}")
                await asyncio.sleep(0.3)
        return False


    async def _fit_page_to_window(self, page) -> float:
        """確保登入頁所有元素都在視窗內；必要時自動縮小頁面縮放。

        以「最底部元素的 bottom」與「視窗可見高度」比較（比 scrollHeight 更準確，
        因為部分版面用絕對定位或置中，且 scrollHeight 不反映 CSS zoom）。
        每次迭代都以「目前已套用的縮放」為基準計算新比例，避免過度縮小。
        """
        try:
            metrics = await _measure_fit_page(page)
        except Exception:
            return 1.0

        inner = metrics.get("innerH") or 0
        bottom = metrics.get("bottomMost") or 0
        if not inner or bottom <= inner - 4:
            return 1.0  # 已完整可見（保留 4px 邊距）

        applied = 1.0
        for _ in range(4):
            ratio = (inner - 4) / bottom
            candidate = max(MIN_ZOOM, min(1.0, applied * ratio * 0.98))
            if candidate >= applied:
                break  # 已達最小縮放或不需再縮
            applied = round(candidate, 3)
            try:
                await page.evaluate(
                    """(s) => {
                        let el = document.getElementById('__fit_style');
                        if (!el) {
                            el = document.createElement('style');
                            el.id = '__fit_style';
                            document.head.appendChild(el);
                        }
                        el.textContent = 'html { zoom: ' + s + ' !important; }';
                    }""",
                    applied,
                )
            except Exception:
                break
            await asyncio.sleep(0.35)
            try:
                again = await _measure_fit_page(page)
            except Exception:
                break
            inner = again.get("innerH") or inner
            bottom = again.get("bottomMost") or bottom
            if bottom <= inner - 4:
                break

        if applied < 1.0:
            logger.info(f"登入頁自動縮放至 {int(applied * 100)}%（確保內容完整可見）")
        return applied

    async def capture_login(
        self,
        account: Account,
        cfg,
        timeout_seconds: int | None = None,
        on_stage: Callable[[str, str], Any] | None = None,
        cancel: asyncio.Event | None = None,
    ) -> LoginResult:
        """開啟顯示視窗、**直接跳到 MiniMax 登入頁**，等使用者完成登入。

        流程：網路預檢 → 啟動瀏覽器 → 載入首頁 → 點擊官方 Sign in 進入
        ``account.minimax.io/unified-login`` → 通知使用者「登入頁已就緒」→ 等待登入完成。

        會即時偵測：視窗被關閉、使用者取消、連線失敗，並回傳可讀的錯誤訊息。
        """
        timeout = max(60, int(timeout_seconds or LOGIN_TIMEOUT_SECONDS))

        if cancel is not None and cancel.is_set():
            return LoginResult(error="cancelled", message=t("login.error.cancelled"))

        # 0) 若簽到正在進行，先告知使用者並等待，避免兩者互搶瀏覽器
        if self.operation.locked():
            await self._notify(on_stage, "waiting_run", t("login.stage.waiting_run"))
        await self.operation.acquire()
        operation_acquired = True

        context: BrowserContext | None = None
        try:
            # 1) 快速網路預檢：連不上就別讓使用者空等
            reachable, reason = await asyncio.to_thread(quick_reachability_check)
            if not reachable:
                return LoginResult(error="network", message=reason)

            await self._notify(on_stage, "launching", t("login.stage.launching"))
            await self.ensure(headless=False, channel=cfg.browser_channel, proxy=cfg.proxy)
            assert self._browser is not None

            state = self.accounts.load_state(account)
            context = await self._browser.new_context(**self._context_kwargs(cfg, state, headed=True))
            page = await context.new_page()

            # 固定尺寸置中（--window-size 在部分環境可能無效，CDP 再確認一次）
            centered = await self._center_login_window(context, page)
            if not centered:
                logger.debug("無法確認登入視窗已置中，稍後會自動縮放頁面以完整顯示")

            closed = asyncio.Event()
            page.on("close", lambda *_: closed.set())
            context.on("close", lambda *_: closed.set())

            # 1) 載入首頁（失敗即回報可讀原因）
            await self._notify(on_stage, "opening", t("login.stage.opening"))
            try:
                response = await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
            except PlaywrightError as exc:
                kind, message = classify_navigation_error(exc)
                logger.warning(f"載入 MiniMax 失敗（{kind}）：{exc}")
                return LoginResult(error=kind, message=message)
            if response is not None and response.status >= 400:
                return LoginResult(
                    error="blocked",
                    message=t("login.error.http", status=response.status),
                )

            # 2) 直接進入官方登入頁（由網站自行產生 OAuth 參數，最穩定）
            await self._notify(on_stage, "opening", t("login.stage.opening_login"))
            entered = await self._enter_login_page(page)

            # 3) 登入頁載入後「再次」確認視窗位置。
            #    Chromium 有時會在首次導航後把視窗恢復成建立時的尺寸，
            #    因此導航前設定一次、導航後再驗證一次，確保使用者看到時已置中。
            if entered:
                await self._center_login_window(context, page)

            # 3) 已經登入（沿用既有 session）→ 直接完成
            if not entered and await self.is_logged_in(page):
                return await self._finish_login(context, page)

            if not entered or LOGIN_HOST not in page.url:
                return LoginResult(
                    error="timeout",
                    message=t("login.error.timeout_page"),
                )

            # 4) 登入頁已就緒，等使用者操作
            await self._notify(on_stage, "fitting", t("login.stage.fitting"))
            scale = await self._fit_page_to_window(page)
            note = t("login.stage.scaled", pct=int(scale * 100)) if scale < 1.0 else ""
            await self._notify(
                on_stage, "ready", t("login.stage.ready", note=note)
            )
            logger.info("登入頁面已開啟，等待使用者完成登入…")

            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if closed.is_set():
                    return LoginResult(error="closed", message=t("login.error.closed"))
                if cancel is not None and cancel.is_set():
                    return LoginResult(error="cancelled", message=t("login.error.cancelled"))
                if await self.is_logged_in(page):
                    return await self._finish_login(context, page)
                await asyncio.sleep(1.5)

            return LoginResult(
                error="timeout",
                message=t("login.error.timeout_wait", minutes=max(1, timeout // 60)),
            )
        except BrowserLaunchError as exc:
            return LoginResult(error="no_browser", message=str(exc))
        except PlaywrightError as exc:
            logger.warning(f"登入流程瀏覽器錯誤：{exc}")
            return LoginResult(
                error="unknown", message=t("login.error.browser", detail=str(exc).splitlines()[0][:120])
            )
        except Exception as exc:  # pragma: no cover - 保底
            logger.exception("登入流程未預期錯誤")
            return LoginResult(error="unknown", message=t("login.error.fail", detail=exc))
        finally:
            if context is not None:
                try:
                    await context.close()
                except Exception:
                    pass
            # 只放自己拿的 operation 鎖；gate 是簽到流程的，不在此釋放，
            # 否則登入結束會提前放掉簽到手上的 gate，造成 headed/headless 互搶。
            if operation_acquired and self.operation.locked():
                self.operation.release()

    # ------------------------------------------------------------------
    @staticmethod
    async def is_logged_in(page) -> bool:
        try:
            if await page.locator(LOGIN_STATE_SIGNED_IN).count() > 0:
                return True
            token = await page.evaluate("() => localStorage.getItem('_token')")
            if not token:
                return False
            if "agent.minimax.io" not in page.url:
                return False
            return len(str(token).split(".")) == 3
        except Exception:
            return False

    @staticmethod
    async def read_user_info(page) -> dict[str, Any]:
        """從 localStorage 取得使用者資訊（顯示名稱、user id、頭像）。"""
        info: dict[str, Any] = {"user_name": "", "user_id": "", "avatar": ""}
        try:
            raw = await page.evaluate("() => localStorage.getItem('user_detail_agent')")
            if raw:
                data = json.loads(raw)
                info["user_name"] = data.get("userName") or data.get("subUserName") or ""
                info["user_id"] = str(data.get("realUserID") or data.get("userID") or "")
                info["avatar"] = data.get("accountAvatarUrl") or ""
        except Exception:
            pass
        if not info["user_id"]:
            try:
                token = await page.evaluate("() => localStorage.getItem('_token')")
                payload = str(token).split(".")[1]
                payload += "=" * (-len(payload) % 4)
                data = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
                user = data.get("user") or {}
                info["user_id"] = str(user.get("id") or "")
                info["user_name"] = info["user_name"] or str(user.get("name") or "")
                info["avatar"] = info["avatar"] or str(user.get("avatar") or "")
            except Exception:
                pass
        return info
