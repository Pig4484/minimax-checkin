"""登入視窗被裁切 — 重現／驗證腳本（不開 headed 視窗、不碰真實帳號）。

方案 B（固定視窗置中）：登入一律 LOGIN_VIEWPORT＋視窗 1100x720 置中＋縮放兜底。
未修復時 [A]/[B] 會失敗；修復後應全數 OK。

用法:
    .\\.venv\\Scripts\\python.exe tools/repro_login_window.py
    .\\.venv\\Scripts\\python.exe tools/repro_login_window.py --with-browser
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import AppConfig
from app.core.account import AccountManager
from app.core.browser import (
    HEADED_LAUNCH_ARGS,
    LOGIN_VIEWPORT,
    LOGIN_WINDOW_HEIGHT,
    LOGIN_WINDOW_WIDTH,
    VIEWPORT,
    BrowserManager,
)


# 模擬 MiniMax 登入頁：置中卡片 + 底部連結（貼近真實登入頁）
LOGIN_LIKE_HTML = """<html><head><style>
body{margin:0;font-family:sans-serif;background:#fff;display:flex;
flex-direction:column;align-items:center}
.card{width:640px;margin-top:60px;text-align:center}
button{width:100%;height:52px;margin:8px 0;border-radius:8px}
.footer{margin:24px 0 8px;color:#666;font-size:13px}
</style></head><body><div class="card"><h1>Welcome to MiniMax</h1>
<button>Continue</button><div>OR</div>
<button>Continue with Google</button>
<button>Continue with Apple</button>
<button>Continue With Github</button>
<div style="height:340px"></div>
<div class="footer">Privacy Policy | Terms of Service</div>
</div></body></html>"""


def check_context_kwargs() -> dict:
    """檢查 A：登入組合（全域 headless=True）必須拿到 LOGIN_VIEWPORT。"""
    browser = BrowserManager(AccountManager(encrypt=False))
    cfg = AppConfig()  # 預設 headless=True
    assert cfg.headless is True, "前置假設改變：AppConfig 預設應為 headless=True"
    kwargs = browser._context_kwargs(cfg, None, headed=True)
    print(f"[A] 登入 headed=True 時 _context_kwargs -> {kwargs}")
    if kwargs.get("viewport") == LOGIN_VIEWPORT:
        print("[A] OK：登入拿到 LOGIN_VIEWPORT，不再被全域 headless 污染")
    else:
        print("[A] 失敗：登入沒拿到 LOGIN_VIEWPORT（修復前會拿到 1440x900）")
    return kwargs


def check_overflow() -> tuple:
    """檢查 B：登入視窗外框必須塞進本機工作區。"""
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication(sys.argv)
        g = app.primaryScreen().availableGeometry()
        avail_w, avail_h = g.width(), g.height()
        print(f"[B] 本機工作區 available={avail_w}x{avail_h}（已扣工作列）")
    except Exception as exc:
        avail_w, avail_h = 1280, 752
        print(f"[B] 取不到螢幕（{exc}），改用實測值 {avail_w}x{avail_h}")
    vw, vh = LOGIN_WINDOW_WIDTH, LOGIN_WINDOW_HEIGHT
    ow, oh = max(0, vw - avail_w), max(0, vh - avail_h)
    print(f"[B] 登入視窗 {vw}x{vh} -> 寬溢出 {ow}px，高溢出 {oh}px"
          + ("（>0 會被工作列切掉）" if oh > 0 else "（OK，塞得下工作區）"))
    flag = f"--window-size={vw},{vh}"
    if flag in HEADED_LAUNCH_ARGS and "--start-maximized" not in HEADED_LAUNCH_ARGS:
        print(f"[B] OK：啟動參數為固定尺寸（{flag}），不再用 --start-maximized")
    else:
        print("[B] 失敗：啟動參數仍用 --start-maximized 或尺寸不符")
        oh = max(oh, 1)
    # 附帶：舊 1440x900 會溢出多少（證明修復前確實塞不下）
    print(f"[B] 對照：舊 VIEWPORT={VIEWPORT['width']}x{VIEWPORT['height']} "
          f"→ 高溢出 {max(0, VIEWPORT['height'] - avail_h)}px（修復前）")
    return avail_w, avail_h, oh


def check_maximize_early_return() -> bool:
    """檢查 C：登入改用 _center_login_window 置中，不再依賴最大化。"""
    ok = hasattr(BrowserManager, "_center_login_window")
    print(f"[C] _center_login_window 存在？{ok}")
    if ok:
        print("[C] OK：登入改走固定尺寸置中（_maximize_window 僅歷史保留）")
    else:
        print("[C] 失敗：缺少置中方法")
    return ok

async def check_fit_with_browser(aw: int, ah: int) -> None:
    """檢查 D（需 --with-browser）：量測登入頁溢出與縮放兜底。"""
    from playwright.async_api import async_playwright

    from app.core.browser import _measure_fit_page

    async with async_playwright() as pw:
        browser = None
        for args in ({"channel": "chromium"}, {}):
            try:
                browser = await pw.chromium.launch(headless=True, **args)
                break
            except Exception:
                continue
        if browser is None:
            print("[D] 跳過：無法啟動 Chromium")
            return
        try:
            ctx = await browser.new_context(viewport=dict(LOGIN_VIEWPORT))
            page = await ctx.new_page()
            await page.set_content(LOGIN_LIKE_HTML)
            await page.wait_for_timeout(400)
            m = await _measure_fit_page(page)
            inner, bottom = m.get("innerH", 0), m.get("bottomMost", 0)
            scale = await BrowserManager._fit_page_to_window(None, page)
            print(f"[D-登入viewport] innerH={inner} bottomMost={bottom} "
                  f"溢出={max(0, bottom - inner)}px scale={scale}（縮放兜底應觸發）")
            await ctx.close()
            ctx2 = await browser.new_context(viewport={"width": aw, "height": ah})
            page2 = await ctx2.new_page()
            await page2.set_content(LOGIN_LIKE_HTML)
            await page2.wait_for_timeout(400)
            m2 = await _measure_fit_page(page2)
            inner2, bottom2 = m2.get("innerH", 0), m2.get("bottomMost", 0)
            scale2 = await BrowserManager._fit_page_to_window(None, page2)
            print(f"[D-工作區尺寸] innerH={inner2} bottomMost={bottom2} "
                  f"溢出={max(0, bottom2 - inner2)}px scale={scale2}")
            await ctx2.close()
        finally:
            await browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="登入視窗裁切重現腳本")
    parser.add_argument("--with-browser", action="store_true")
    args = parser.parse_args()
    print("=== 登入視窗裁切重現 ===")
    kwargs = check_context_kwargs()
    aw, ah, oh = check_overflow()
    centered = check_maximize_early_return()
    if args.with_browser:
        asyncio.run(check_fit_with_browser(aw, ah))
    ok = kwargs.get("viewport") == LOGIN_VIEWPORT and oh <= 0 and centered
    print()
    if ok:
        print("結論：OK —— 登入視窗 1100x720 置中＋LOGIN_VIEWPORT＋縮放兜底")
        return 0
    print("結論：失敗 —— 仍有檢查未通過（見上方 [A]/[B]/[C]）")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

