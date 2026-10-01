"""選擇器引擎測試：以實測擷取的 HTML fixture 離線驗證（不需連線 MiniMax）。"""

from __future__ import annotations

from app.constants import SIGNIN_CARD
from app.core import selectors

MINIMAL_PAGE = "<html><body><h1>MiniMax makes your work easier</h1></body></html>"


def test_finds_claim_button_on_available_panel(async_browser, panel_html):
    loop, browser = async_browser

    async def scenario():
        page = await browser.new_page()
        try:
            await page.set_content(panel_html)
            assert await selectors.panel_present(page) is True
            match = await selectors.find_claim_button(page)
            assert match is not None, "應該能在面板中找到簽到按鈕"
            assert match.selector == "button.signin-claim-button"
            assert match.kind == "class"
            assert match.aria == "Check in for 800 Credits"
            assert match.disabled is False
            assert match.looks_claimed is False
            assert await selectors.button_state(page) == "available"
        finally:
            await page.close()

    loop.run_until_complete(scenario())


def test_reads_panel_days(async_browser, panel_html):
    loop, browser = async_browser

    async def scenario():
        page = await browser.new_page()
        try:
            await page.set_content(panel_html)
            days = await selectors.panel_days(page)
            assert len(days) == 7
            assert days[0]["day_no"] == 1
            assert days[0]["today"] is True
            assert days[0]["text"] == "800"
            assert days[3]["text"] == "2,000"
            fingerprint = await selectors.structural_fingerprint(page)
            assert len(fingerprint) == 16
        finally:
            await page.close()

    loop.run_until_complete(scenario())


def test_claimed_panel_is_detected(async_browser, claimed_panel_html):
    loop, browser = async_browser

    async def scenario():
        page = await browser.new_page()
        try:
            await page.set_content(claimed_panel_html)
            match = await selectors.find_claim_button(page)
            assert match is not None
            assert match.looks_claimed is True, "停用/Checked in 的按鈕應判定為已領取"
            assert await selectors.button_state(page) == "claimed"
        finally:
            await page.close()

    loop.run_until_complete(scenario())


def test_missing_panel_reports_missing(async_browser):
    """官方在已簽到當日完全不渲染面板 → 應回報 missing（由 API 狀態決定結果）。"""
    loop, browser = async_browser

    async def scenario():
        page = await browser.new_page()
        try:
            await page.set_content(MINIMAL_PAGE)
            assert await selectors.panel_present(page) is False
            assert await selectors.find_claim_button(page) is None
            assert await selectors.button_state(page) == "missing"
            scan = await selectors.heuristic_scan(page)
            assert scan["panel_present"] is False
            assert scan["claim_candidates"] == []
        finally:
            await page.close()

    loop.run_until_complete(scenario())


def test_scan_reports_candidates_for_diagnostics(async_browser, panel_html):
    loop, browser = async_browser

    async def scenario():
        page = await browser.new_page()
        try:
            await page.set_content(panel_html)
            scan = await selectors.heuristic_scan(page)
            assert scan["panel_present"] is True
            claims = [c for c in scan["claim_candidates"] if c["aria"].startswith("Check in for")]
            assert claims, "診斷掃描應列出簽到按鈕"
            assert claims[0]["testid"] == ""
            assert SIGNIN_CARD.strip("[]").split("=")[0] in SIGNIN_CARD
        finally:
            await page.close()

    loop.run_until_complete(scenario())
