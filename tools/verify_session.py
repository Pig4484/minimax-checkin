"""對真實站台執行一次簽到驗證（使用應用程式已儲存的 session）。

用途：確認目前版本的選擇器與流程對 MiniMax 仍有效。
注意：若帳號今日尚未簽到，**這個指令會真的完成簽到**。

用法::

    python tools/verify_session.py                  # 驗證全部啟用中的帳號
    python tools/verify_session.py --account "呂俊傑"
    python tools/verify_session.py --headed         # 顯示瀏覽器視窗
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import AppConfig  # noqa: E402
from app.constants import SELECTOR_PACK_VERSION  # noqa: E402
from app.core.account import AccountManager  # noqa: E402
from app.core.browser import BrowserManager  # noqa: E402
from app.core.engine import CheckinEngine  # noqa: E402
from app.core.state import RunStateStore  # noqa: E402
from app.logger import enable_utf8_console, logger, setup  # noqa: E402


async def verify(alias: str | None, headed: bool) -> int:
    cfg = AppConfig.load()
    if headed:
        cfg.headless = False
    cfg.fallback_headed = False

    manager = AccountManager(encrypt=cfg.encrypt_sessions)
    if alias:
        account = next(
            (a for a in manager.accounts if a.display_name == alias or a.user_name == alias), None
        )
        targets = [account.id] if account else []
    else:
        targets = [a.id for a in manager.enabled_accounts()]

    if not targets:
        logger.error("沒有可驗證的帳號（請先在 GUI 新增並登入帳號）")
        return 2

    browser = BrowserManager(manager)
    engine = CheckinEngine(cfg, manager, browser, RunStateStore())
    try:
        await browser.start(headless=cfg.headless, channel=cfg.browser_channel, proxy=cfg.proxy)
        results = await engine.run(reason="verify", only_ids=targets)
    finally:
        await browser.stop()

    print("\n=== 驗證結果（選擇器包 v%d） ===" % SELECTOR_PACK_VERSION)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    ok = all(r["ok"] for r in results)
    print("\n結論：" + ("✅ 簽到流程正常" if ok else "❌ 有帳號未成功，請查看上方訊息與診斷目錄"))
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="MiniMax 簽到流程驗證")
    parser.add_argument("--account", help="帳號別名或登入名稱（預設驗證全部）")
    parser.add_argument("--headed", action="store_true", help="顯示瀏覽器視窗")
    args = parser.parse_args()
    enable_utf8_console()
    setup("INFO", 7)
    return asyncio.run(verify(args.account, args.headed))


if __name__ == "__main__":
    raise SystemExit(main())
