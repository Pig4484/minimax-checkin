"""彈窗／遮罩處理測試。

背景：官方「The Latest MiniMax Code Update Is Here.」公告彈窗以 `fixed inset-0 z-[9999]`
蓋住整頁並攔截 pointer events，會讓簽到按鈕點不到（Playwright click 逾時）。
2026-09-29 實測重現後加入自動關閉邏輯，這裡以擷取到的 markup 建立回歸測試。
"""

from __future__ import annotations

from app.core.checkin import OVERLAY_SELECTORS, _dismiss_overlays

MODAL = '[aria-modal="true"]'


def test_dismiss_closes_blocking_modal(async_browser, modal_html):
    loop, browser = async_browser

    async def scenario():
        page = await browser.new_page()
        try:
            await page.set_content(modal_html)
            assert await page.locator(MODAL).count() == 1, "fixture 應該包含遮罩彈窗"

            handled = await _dismiss_overlays(page, "測試")

            assert handled is True, "偵測到遮罩時應回報已處理"
            assert await page.locator(MODAL).count() == 0, "遮罩應被關閉或移除"
            # 移除遮罩後，簽到按鈕必須可以正常點擊（不再被攔截）
            await page.locator("button.signin-claim-button").click(timeout=5000)
        finally:
            await page.close()

    loop.run_until_complete(scenario())


def test_dismiss_is_noop_without_modal(async_browser, panel_html):
    loop, browser = async_browser

    async def scenario():
        page = await browser.new_page()
        try:
            await page.set_content(panel_html)
            handled = await _dismiss_overlays(page, "測試")
            assert handled is False, "沒有遮罩時不應有任何處理動作"
            assert await page.locator('[data-testid="signin-card"]').count() == 1
        finally:
            await page.close()

    loop.run_until_complete(scenario())


def test_overlay_selectors_cover_known_markup(modal_html):
    """確認選擇器仍能對應官方目前的彈窗 markup。"""
    assert 'aria-modal="true"' in modal_html
    assert "bg-utility_overlay" in modal_html
    assert '[aria-modal="true"]' in OVERLAY_SELECTORS
    assert "div.bg-utility_overlay" in OVERLAY_SELECTORS
