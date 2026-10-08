"""簽到登入判定測試：API 優先、拿不到回應時不誤判 NEED_RELOGIN。"""
from __future__ import annotations

import asyncio

from playwright.async_api import Error as PlaywrightError

from app.constants import DayStatus, RunStatus
from app.core.account import AccountManager
from app.core.checkin import run_account_checkin
from app.core import checkin as checkin_module


def _cfg():
    class Cfg:
        timeout_seconds = 5
        keep_browser_open = False

    return Cfg()


def test_api_available_means_logged_in_despite_signed_out_dom(temp_root, status_available):
    """API 顯示 today.status=2（可簽）時，即使 DOM 有登出按鈕也不得判 NEED_RELOGIN。

    背景：舊邏輯只看 DOM＋localStorage，頁面 hydrate 前就採樣會誤判，
    明明能簽到卻叫使用者重登。
    """
    from app.constants import LOGIN_STATE_SIGNED_OUT

    manager = AccountManager(encrypt=False)
    account = manager.add("A")
    manager.save_state(account, {"cookies": [], "origins": []})

    class FakeLocator:
        async def count(self):
            return 1  # 假裝看到登出按鈕（hydrate 前的誤判現場）

    class FakeWaiter:
        async def json(self):
            return status_available

    class FakeResponse:
        async def __aenter__(self):
            return FakeWaiter()

        async def __aexit__(self, *a):
            return False

    class FakePage:
        url = "https://agent.minimax.io/"

        def locator(self, selector):
            assert selector == LOGIN_STATE_SIGNED_OUT
            return FakeLocator()

        async def evaluate(self, expr):
            return None  # 假裝 localStorage 沒 token

        def expect_response(self, *a, **k):
            return FakeResponse()

        async def goto(self, *a, **k):
            return None

    class FakeContext:
        async def new_page(self):
            return FakePage()

        async def close(self):
            return None

    class FakeBrowser:
        async def new_context(self, account, cfg):
            return FakeContext()

        async def update_state(self, account, context):
            return None

    outcome = asyncio.run(
        run_account_checkin(manager, FakeBrowser(), account, _cfg(), diag_folder=temp_root)
    )
    # 有 API 回應且 today 可簽 → 不得回 NEED_RELOGIN（後續走面板等待，此處只斷言判定層）
    assert outcome.status != RunStatus.NEED_RELOGIN, f"誤判重登：{outcome.message}"


def test_page_closed_returns_failed_not_need_relogin(temp_root):
    """頁面被關閉（expect_response 拋 closed）時回 FAILED，不寫 NEED_RELOGIN。"""
    manager = AccountManager(encrypt=False)
    account = manager.add("A")
    manager.save_state(account, {"cookies": [], "origins": []})

    class FakePage:
        url = "https://agent.minimax.io/"

        def expect_response(self, *a, **k):
            raise PlaywrightError("Target page, context or browser has been closed")

        async def goto(self, *a, **k):
            return None

    class FakeContext:
        async def new_page(self):
            return FakePage()

        async def close(self):
            return None

    class FakeBrowser:
        async def new_context(self, account, cfg):
            return FakeContext()

        async def update_state(self, account, context):
            return None

    outcome = asyncio.run(
        run_account_checkin(manager, FakeBrowser(), account, _cfg(), diag_folder=temp_root)
    )
    assert outcome.status == RunStatus.FAILED
    assert "重" not in outcome.message or "登入" not in outcome.message


def test_browser_imports_playwright_timeout():
    """迴歸：browser.py 必須匯入 PlaywrightTimeout，否則登入頁等待逾時變 NameError。"""
    import app.core.browser as browser_module

    assert hasattr(browser_module, "PlaywrightTimeout")