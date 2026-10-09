"""登入流程相關測試：錯誤分類、網路預檢、視窗關閉偵測。"""

from __future__ import annotations

import asyncio

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeout

from app.core.browser import (
    LoginResult,
    classify_navigation_error,
    quick_reachability_check,
)


class FakePlaywrightTimeout(PlaywrightTimeout):
    pass


def test_classify_dns_error():
    kind, message = classify_navigation_error(
        Exception("net::ERR_NAME_NOT_RESOLVED at https://agent.minimax.io/")
    )
    assert kind == "network"
    assert "網路" in message


def test_classify_offline_error():
    kind, _ = classify_navigation_error(Exception("net::ERR_INTERNET_DISCONNECTED"))
    assert kind == "network"


def test_classify_proxy_error():
    kind, message = classify_navigation_error(Exception("net::ERR_PROXY_CONNECTION_FAILED"))
    assert kind == "proxy"
    assert "代理" in message


def test_classify_ssl_error():
    kind, _ = classify_navigation_error(Exception("net::ERR_SSL_PROTOCOL_ERROR"))
    assert kind == "ssl"


def test_classify_timeout_error():
    kind, message = classify_navigation_error(Exception("Timeout 30000ms exceeded"))
    assert kind == "timeout"
    assert "逾時" in message


def test_classify_blocked_error():
    kind, _ = classify_navigation_error(Exception("net::ERR_BLOCKED_BY_CLIENT"))
    assert kind == "blocked"


def test_classify_unknown_error():
    kind, message = classify_navigation_error(Exception("something odd happened"))
    assert kind == "unknown"
    assert message.startswith("無法載入網頁")


def test_reachability_check_accepts_known_host():
    """對真實主機做一次預檢；離線環境下應回傳失敗而非拋例外。"""
    ok, message = quick_reachability_check("agent.minimax.io", timeout=6.0)
    assert isinstance(ok, bool)
    if not ok:
        assert message, "失敗時必須提供可讀原因"


def test_reachability_check_bad_host_returns_reason():
    ok, message = quick_reachability_check("this-host-should-not-exist.invalid", timeout=4.0)
    assert ok is False
    assert message


def test_login_result_defaults():
    result = LoginResult()
    assert result.ok is False
    assert result.state is None
    assert result.error == ""


def test_login_result_success_shape():
    result = LoginResult(ok=True, state={"cookies": []}, info={"user_name": "測試"})
    assert result.ok and result.state == {"cookies": []}
    assert result.info["user_name"] == "測試"


def test_manager_has_operation_lock():
    """必須有長期操作鎖，避免「簽到(headless)」與「登入(headed)」互相重啟瀏覽器。"""
    import asyncio as aio

    from app.core.account import AccountManager
    from app.core.browser import BrowserManager

    browser = BrowserManager(AccountManager(encrypt=False))
    assert hasattr(browser, "operation"), "缺少長期操作鎖"
    assert isinstance(browser.operation, type(aio.Lock()))


def test_engine_run_uses_operation_lock(temp_root):
    """整輪簽到必須在 operation 鎖內執行，否則會與登入互搶瀏覽器。"""
    import asyncio as aio

    from app.config import AppConfig
    from app.core.account import AccountManager
    from app.core.engine import CheckinEngine
    from app.core.state import RunStateStore

    seen: list[bool] = []

    class FakeBrowser:
        def __init__(self):
            self.operation = aio.Lock()

        async def new_context(self, account, cfg):
            # 執行期間鎖必須是「已被持有」的狀態
            seen.append(self.operation.locked())
            raise RuntimeError("測試用：不真的開瀏覽器")

    cfg = AppConfig()
    accounts = AccountManager(encrypt=False)
    account = accounts.add("測試")
    # 必須有 session，否則流程會提早以 NEED_RELOGIN 結束而不建立 context
    accounts.save_state(account, {"cookies": [], "origins": []})
    browser = FakeBrowser()
    engine = CheckinEngine(cfg, accounts, browser, RunStateStore())

    results = aio.run(engine.run("manual"))
    assert seen and all(seen), f"每次建立 context 時都應處於 operation 鎖內，實際 {seen}"
    assert results and results[0]["ok"] is False  # 失敗但流程正確結束
    assert not browser.operation.locked(), "結束後必須釋放鎖"


def test_capture_login_reports_waiting_stage(monkeypatch, temp_root):
    """簽到進行中時，登入應先回報「等待簽到結束」而不是搶走瀏覽器。"""
    import asyncio as aio

    from app.core.account import AccountManager
    from app.core import browser as browser_module
    from app.core.browser import BrowserLaunchError, BrowserManager

    monkeypatch.setattr(browser_module, "quick_reachability_check", lambda *a, **k: (True, ""))

    async def fake_ensure(self, *args, **kwargs):  # 不真的啟動瀏覽器
        raise BrowserLaunchError("測試用：不啟動瀏覽器")

    monkeypatch.setattr(BrowserManager, "ensure", fake_ensure)

    manager = AccountManager(encrypt=False)
    account = manager.add("測試")
    browser = BrowserManager(manager)
    stages: list[str] = []

    async def scenario():
        await browser.operation.acquire()  # 模擬簽到進行中
        task = aio.create_task(
            browser.capture_login(
                account,
                _FakeCfg(),
                on_stage=lambda s, m: stages.append(s),
                cancel=aio.Event(),
            )
        )
        await aio.sleep(0.3)
        assert "waiting_run" in stages, f"應先回報等待中，實際 {stages}"
        browser.operation.release()  # 讓登入繼續
        result = await aio.wait_for(task, timeout=10)
        assert result.ok is False
        assert result.error == "no_browser"
        return True

    assert aio.run(scenario()) is True


def test_capture_login_aborts_immediately_when_cancelled(monkeypatch, temp_root):
    """已取消時應立刻回傳，不啟動瀏覽器。"""
    from app.core.account import AccountManager
    from app.core.browser import BrowserManager

    manager = AccountManager(encrypt=False)
    account = manager.add("測試")
    browser = BrowserManager(manager)

    cancel = asyncio.Event()
    cancel.set()

    result = asyncio.run(
        browser.capture_login(account, _FakeCfg(), cancel=cancel)
    )
    assert result.ok is False
    assert result.error == "cancelled"
    assert browser._browser is None, "已取消時不應啟動瀏覽器"


def test_browser_has_window_helpers():
    """登入視窗置中與自動縮放的輔助方法必須存在（方案 B：固定尺寸置中）。"""
    from app.core.browser import BrowserManager

    assert hasattr(BrowserManager, "_center_login_window"), "缺少 CDP 固定尺寸置中"
    assert hasattr(BrowserManager, "_maximize_window"), "舊最大化方法保留（歷史相容）"
    assert hasattr(BrowserManager, "_fit_page_to_window"), "缺少頁面自動縮放"
    assert hasattr(BrowserManager, "_context_kwargs"), "缺少共用 context 選項"


def test_headed_context_uses_no_viewport():
    """登入（headed=True）必須用 LOGIN_VIEWPORT，不再受全域 cfg.headless 影響。"""
    from app.core.account import AccountManager
    from app.core.browser import LOGIN_VIEWPORT, BrowserManager

    browser = BrowserManager(AccountManager(encrypt=False))

    class Cfg:
        headless = False
        custom_user_agent = ""

    headed = browser._context_kwargs(Cfg(), None, headed=True)
    assert headed.get("viewport") == LOGIN_VIEWPORT
    assert "no_viewport" not in headed

    # 關鍵迴歸：全域 headless=True（預設）時，登入仍必須拿到登入專用 viewport
    Cfg.headless = True
    login_kwargs = browser._context_kwargs(Cfg(), None, headed=True)
    assert login_kwargs.get("viewport") == LOGIN_VIEWPORT, (
        "登入被全域 headless 污染，拿到簽到用的 1440x900 → 底部會被工作列切掉"
    )

    headless_kwargs = browser._context_kwargs(Cfg(), None)
    assert "viewport" in headless_kwargs
    assert "no_viewport" not in headless_kwargs


def test_headed_launch_args_include_maximize():
    from app.core.browser import (
        HEADED_LAUNCH_ARGS,
        LAUNCH_ARGS,
        LOGIN_WINDOW_HEIGHT,
        LOGIN_WINDOW_WIDTH,
    )

    assert f"--window-size={LOGIN_WINDOW_WIDTH},{LOGIN_WINDOW_HEIGHT}" in HEADED_LAUNCH_ARGS
    assert "--start-maximized" not in HEADED_LAUNCH_ARGS, "方案 B 改用固定尺寸置中，不再最大化"
    assert "--start-maximized" not in LAUNCH_ARGS, "無頭模式不需要最大化參數"
    assert "--disable-blink-features=AutomationControlled" in HEADED_LAUNCH_ARGS


def test_fit_page_to_window_scales_when_content_too_tall(async_browser):
    """頁面比視窗高時應套用縮放；否則維持 1.0。"""
    from app.core.browser import BrowserManager

    loop, browser = async_browser

    async def scenario():
        page = await browser.new_page(viewport={"width": 800, "height": 300})
        try:
            await page.set_content(
                "<html><body style='margin:0'><div style='height:1200px;background:#eee'>"
                "</div></body></html>"
            )
            scale = await BrowserManager._fit_page_to_window(None, page)
            assert scale < 1.0, f"內容過高時應縮放，實際 {scale}"
            applied = await page.evaluate(
                "() => getComputedStyle(document.documentElement).zoom"
            )
            assert abs(float(applied) - scale) < 0.01

            await page.set_content("<html><body style='margin:0'><div>短</div></body></html>")
            assert await BrowserManager._fit_page_to_window(None, page) == 1.0
        finally:
            await page.close()

    loop.run_until_complete(scenario())


def test_capture_login_reports_network_failure(monkeypatch, temp_root):
    """網路預檢失敗時應立刻回報，且訊息可讀。"""
    from app.core.account import AccountManager
    from app.core import browser as browser_module
    from app.core.browser import BrowserManager

    monkeypatch.setattr(
        browser_module, "quick_reachability_check", lambda *a, **k: (False, "測試用：無法連線")
    )
    manager = AccountManager(encrypt=False)
    account = manager.add("測試")
    browser = BrowserManager(manager)

    result = asyncio.run(browser.capture_login(account, _FakeCfg()))
    assert result.ok is False
    assert result.error == "network"
    assert result.message == "測試用：無法連線"
    assert browser._browser is None, "連線失敗時不應啟動瀏覽器"


class _FakeCfg:
    headless = True
    browser_channel = "chromium"
    proxy = ""
    custom_user_agent = ""
    timeout_seconds = 30


def test_capture_login_does_not_release_signin_gate(monkeypatch, temp_root):
    """登入結束只放自己的 operation 鎖，不可放掉簽到手上的 gate。"""
    import asyncio as aio

    from app.core.account import AccountManager
    from app.core.browser import BrowserManager

    monkeypatch.setattr(
        "app.core.browser.quick_reachability_check", lambda *a, **k: (False, "測試用：無法連線")
    )
    manager = AccountManager(encrypt=False)
    account = manager.add("測試")
    browser = BrowserManager(manager)

    async def scenario():
        await browser.gate.acquire()  # 模擬簽到進行中持有 gate
        result = await browser.capture_login(account, _FakeCfg())
        assert result.error == "network"
        assert browser.gate.locked(), "登入不可釋放簽到的 gate 鎖"
        assert not browser.operation.locked(), "登入自己的 operation 鎖必須釋放"
        browser.gate.release()

    aio.run(scenario())


def test_fallback_headed_does_not_mutate_shared_cfg(monkeypatch, temp_root):
    """無頭 fallback 必須用副本 cfg 重試，不可翻轉共用的 cfg.headless。"""
    import asyncio as aio

    from app.config import AppConfig
    from app.core import engine as engine_module
    from app.core.account import AccountManager
    from app.core.checkin import CheckinOutcome
    from app.core.engine import CheckinEngine
    from app.core.state import RunStateStore
    from app.constants import RunStatus

    cfg = AppConfig()
    cfg.headless = True
    cfg.fallback_headed = True
    accounts = AccountManager(encrypt=False)
    account = accounts.add("測試")
    accounts.save_state(account, {"cookies": [], "origins": []})

    seen: list[bool] = []

    async def fake_checkin(accounts, browser, account, cfg_arg, **kwargs):
        seen.append(bool(cfg_arg.headless))
        return CheckinOutcome(RunStatus.FAILED, message="測試用失敗")

    monkeypatch.setattr(engine_module, "run_account_checkin", fake_checkin)
    engine = CheckinEngine(cfg, accounts, object(), RunStateStore())
    aio.run(engine.run("manual"))
    assert cfg.headless is True, "共用 cfg.headless 不可被 fallback 翻轉"
    assert seen == [True, False], f"首輪無頭、重試顯示視窗，實際 {seen}"