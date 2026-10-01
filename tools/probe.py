"""獨立頁面掃描工具（MiniMax 改版時用來更新選擇器）。

用法::

    python tools/probe.py                     # 使用第一個帳號的 session
    python tools/probe.py --account "呂俊傑"   # 指定帳號（別名或登入名稱）
    python tools/probe.py --headed            # 顯示瀏覽器視窗

輸出：
- ``%APPDATA%\\MinimaxCheckin\\diagnostics\\<時間>_probe\\`` 內含
  ``probe_scan.json``（面板狀態、指紋、候選元素）與 ``probe.html`` / ``probe.png``
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import AppConfig  # noqa: E402
from app.constants import BASE_URL, SELECTOR_PACK_VERSION  # noqa: E402
from app.core import diagnostics, selectors  # noqa: E402
from app.core.account import AccountManager  # noqa: E402
from app.core.browser import BrowserManager  # noqa: E402
from app.logger import enable_utf8_console, logger, setup  # noqa: E402


async def probe(alias: str | None, headed: bool) -> int:
    cfg = AppConfig.load()
    cfg.headless = not headed
    manager = AccountManager(encrypt=cfg.encrypt_sessions)
    accounts = manager.accounts
    if alias:
        account = next((a for a in accounts if a.display_name == alias or a.user_name == alias), None)
    else:
        account = accounts[0] if accounts else None
    if account is None:
        logger.error("找不到可用帳號（請先在 GUI 新增並登入帳號）")
        return 2
    if not manager.has_state(account):
        logger.error(f"帳號「{account.display_name}」尚未登入")
        return 2

    folder = diagnostics.session_dir(f"{account.display_name}_probe")
    browser = BrowserManager(manager)
    context = None
    try:
        await browser.start(headless=cfg.headless, channel=cfg.browser_channel, proxy=cfg.proxy)
        context = await browser.new_context(account, cfg)
        page = await context.new_page()
        await page.goto(
            BASE_URL, wait_until="domcontentloaded", timeout=max(30, cfg.timeout_seconds) * 1000
        )
        await asyncio.sleep(3)

        scan = await selectors.heuristic_scan(page)
        match = await selectors.find_claim_button(page)
        scan["matched_selector"] = match.selector if match else ""
        scan["selector_pack_version"] = SELECTOR_PACK_VERSION
        scan["account"] = account.display_name
        diagnostics.write_json(folder, "probe_scan.json", scan)
        await diagnostics.capture_page(page, folder, "probe")

        print(json.dumps(scan, ensure_ascii=False, indent=2))
        print(f"\n診斷檔案：{folder}")
        if not scan.get("panel_present"):
            print(
                "面板不存在：可能今日已簽到（正常），或官方已改版（請對照 docs/research/findings.md）"
            )
        elif not match:
            print("⚠️ 面板存在但找不到簽到按鈕 → 選擇器可能已失效，請更新 app/core/selectors.py")
        return 0
    finally:
        if context is not None:
            await context.close()
        await browser.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description="MiniMax 簽到頁面掃描工具")
    parser.add_argument("--account", help="帳號別名或登入名稱（預設使用第一個帳號）")
    parser.add_argument("--headed", action="store_true", help="顯示瀏覽器視窗")
    args = parser.parse_args()
    enable_utf8_console()
    setup("INFO", 7)
    return asyncio.run(probe(args.account, args.headed))


if __name__ == "__main__":
    raise SystemExit(main())
