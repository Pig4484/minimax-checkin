"""單一帳號的簽到流程。

策略（為什麼不用純 HTTP）：官方 API 要求 `x-signature` / `yy` 簽章，實測直接呼叫會回
`HTTP 400 invalid signature`。因此改為 **Playwright 操作真實 UI**（由網站自己的程式碼帶
上正確簽章），並 **攔截官方 API 回應** 取得結構化結果（簽到狀態、獲得點數、失敗原因）。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from playwright.async_api import (
    BrowserContext,
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeout,
)

from app.constants import (
    API_SIGNIN_CLAIM,
    API_SIGNIN_STATUS,
    BASE_URL,
    DayStatus,
    LOGIN_HOST,
    LOGIN_STATE_SIGNED_OUT,
    SIGNIN_CARD,
    RunStatus,
)
from app.core import diagnostics, selectors
from app.core.account import Account, AccountManager
from app.logger import logger


@dataclass
class CheckinOutcome:
    """一次簽到執行的結果。"""

    status: RunStatus
    points: int = 0
    day_no: int = 0
    message: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status.is_ok

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "points": self.points,
            "day_no": self.day_no,
            "message": self.message,
        }


async def _wait_panel(page, timeout_ms: int) -> bool:
    try:
        await page.wait_for_selector(SIGNIN_CARD, state="attached", timeout=timeout_ms)
        return True
    except (PlaywrightTimeout, PlaywrightError):
        return False


async def _has_token(page) -> bool:
    try:
        return bool(await page.evaluate("() => !!localStorage.getItem('_token')"))
    except Exception:
        return False


async def _verify_claimed(page) -> bool:
    """二次驗證：簽到後面板應消失（官方在已簽到當日不渲染面板）。"""
    await asyncio.sleep(1.5)
    try:
        if not await selectors.panel_present(page):
            return True
        return await selectors.button_state(page) != "available"
    except Exception:
        return False


def _points_of(entry: dict[str, Any] | None) -> int:
    try:
        return int((entry or {}).get("points") or 0)
    except (TypeError, ValueError):
        return 0


async def _drift_outcome(page, folder: Path, message: str) -> CheckinOutcome:
    """找不到介面時：留下診斷檔（DOM / 截圖 / 候選元素）並回報 DRIFT。"""
    try:
        scan = await selectors.heuristic_scan(page)
    except Exception:
        scan = {}
    diagnostics.write_json(folder, "drift_scan.json", scan)
    await diagnostics.capture_page(page, folder, "drift")
    logger.warning(message)
    return CheckinOutcome(RunStatus.DRIFT, message=message, detail=scan)


# 會攔截點擊的彈窗／遮罩（例如官方的更新公告：「The Latest MiniMax Code Update Is Here.」）
OVERLAY_SELECTORS = (
    '[role="dialog"][aria-modal="true"]',
    '[aria-modal="true"]',
    "div.bg-utility_overlay",
)

CLOSE_BUTTON_SELECTORS = (
    'button[aria-label*="Close"]',
    'button[aria-label*="close"]',
    'button[aria-label*="關閉"]',
    'button:has-text("Close")',
    'button:has-text("關閉")',
)


async def _dismiss_overlays(page, tag: str) -> bool:
    """關閉會擋住點擊的彈窗；回傳是否有處理到東西。

    依序嘗試：彈窗的關閉鈕 → Escape → 直接移除遮罩節點（僅 UI 元素，不影響簽到請求）。
    """
    handled = False
    for selector in OVERLAY_SELECTORS:
        try:
            if await page.locator(selector).count() == 0:
                continue
        except PlaywrightError:
            continue
        handled = True
        closed = False
        for close_selector in CLOSE_BUTTON_SELECTORS:
            try:
                button = page.locator(f"{selector} {close_selector}").first
                if await button.count() > 0 and await button.is_visible():
                    await button.click(timeout=5000)
                    logger.info(f"[{tag}] 已關閉攔截點擊的彈窗（{close_selector}）")
                    closed = True
                    break
            except PlaywrightError:
                continue
        if not closed:
            try:
                await page.keyboard.press("Escape")
            except PlaywrightError:
                pass
        await asyncio.sleep(0.4)
        try:
            if await page.locator(selector).count() > 0:
                removed = await page.evaluate(
                    """(sels) => {
                        let removed = 0;
                        for (const sel of sels) {
                            document.querySelectorAll(sel).forEach((el) => { el.remove(); removed++; });
                        }
                        return removed;
                    }""",
                    list(OVERLAY_SELECTORS),
                )
                if removed:
                    logger.info(f"[{tag}] 已移除 {removed} 個遮罩元素（{selector}）")
                    await asyncio.sleep(0.3)
        except PlaywrightError:
            pass
    return handled


async def _click_and_wait(page, locator, timeout_ms: int, tag: str):
    """點擊簽到按鈕並等待 claim 回應；被遮擋時會關閉彈窗重試，最後直接派送 click 事件。"""
    response_timeout = min(timeout_ms, 25000)
    for attempt in range(3):
        try:
            async with page.expect_response(
                lambda r: API_SIGNIN_CLAIM in r.url, timeout=response_timeout
            ) as waiter:
                if attempt < 2:
                    await locator.click(timeout=8000)
                else:
                    await locator.dispatch_event("click")
                    logger.info(f"[{tag}] 改以直接派送 click 事件點擊")
            response = await waiter.value
            return await response.json(), ""
        except PlaywrightTimeout as exc:
            detail = str(exc).splitlines()[0][:100] if str(exc) else "逾時"
            if attempt < 2:
                logger.warning(f"[{tag}] 第 {attempt + 1} 次點擊未成功（{detail}），嘗試關閉遮罩後重試")
                await _dismiss_overlays(page, tag)
                continue
            return None, "點擊未成功（可能被彈窗或其他元素阻擋）"
        except PlaywrightError as exc:
            detail = str(exc).splitlines()[0][:100] if str(exc) else "瀏覽器錯誤"
            if attempt < 2:
                logger.warning(f"[{tag}] 第 {attempt + 1} 次點擊失敗（{detail}），重試中")
                await _dismiss_overlays(page, tag)
                continue
            return None, f"點擊失敗：{detail}"
    return None, "點擊未成功"


async def run_account_checkin(
    accounts: AccountManager,
    browser,
    account: Account,
    cfg,
    diag_folder: Path | None = None,
    cancel: asyncio.Event | None = None,
) -> CheckinOutcome:
    """執行單一帳號的簽到流程。"""
    tag = account.display_name
    state = accounts.load_state(account)
    if not state:
        return CheckinOutcome(RunStatus.NEED_RELOGIN, message="尚未登入（沒有可用的 session）")

    folder = diag_folder or diagnostics.session_dir(tag)
    context: BrowserContext | None = None
    timeout_ms = cfg.timeout_seconds * 1000

    try:
        context = await browser.new_context(account, cfg)
        page = await context.new_page()

        status_payload: dict[str, Any] | None = None
        page_closed = False
        try:
            async with page.expect_response(
                lambda r: API_SIGNIN_STATUS in r.url, timeout=timeout_ms
            ) as waiter:
                await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=timeout_ms)
            status_payload = await (await waiter.value).json()
        except PlaywrightTimeout:
            logger.debug(f"[{tag}] 未取得 signin/status 回應")
        except PlaywrightError as exc:
            # 頁面被關閉（例如使用者手動關了簽到視窗）與真正的連線失敗要區分：
            # 前者不代表登入失效，不應寫入 NEED_RELOGIN 誤導使用者重登。
            if "has been closed" in str(exc):
                page_closed = True
                logger.debug(f"[{tag}] 頁面已關閉，中止本次簽到（不判定為登入失效）")
            else:
                logger.debug(f"[{tag}] signin/status 取得失敗：{exc}")

        # --- 登入狀態判定 -------------------------------------------------
        # 判定順序（避免誤判 NEED_RELOGIN）：
        #   1. 有 signin/status 回應 → 以 API 為準（最可靠，不依賴 DOM 時序）。
        #      回應裡的 today.status：2=今日可簽（必已登入）、3=已領取（必已登入）。
        #   2. 無 API 回應 → 才用 DOM＋token 兜底（頁面被關閉時直接回 FAILED）。
        today = selectors.today_entry(status_payload)
        today_status = today.get("status") if today else None
        api_says_logged_in = today_status in (DayStatus.AVAILABLE, DayStatus.CLAIMED)
        if api_says_logged_in:
            logger.debug(f"[{tag}] API 顯示已登入（today.status={today_status}），跳過 DOM 判定")
            signed_out = False
            has_token = True
        elif page_closed or status_payload is None:
            # 連 API 回應都沒拿到（頁面被關／網路中斷）：無法判定登入狀態，
            # 回 FAILED 而非 NEED_RELOGIN，避免明明能簽到卻叫使用者重登。
            return CheckinOutcome(
                RunStatus.FAILED,
                message="未能取得簽到狀態（頁面被關閉或網路中斷），請再試一次",
                detail={"url": page.url},
            )
        else:
            try:
                signed_out = (
                    LOGIN_HOST in page.url
                    or await page.locator(LOGIN_STATE_SIGNED_OUT).count() > 0
                )
            except PlaywrightError:
                signed_out = False
            has_token = await _has_token(page)
        if not api_says_logged_in and (signed_out or not has_token):
            await diagnostics.capture_page(page, folder, "not_logged_in")
            diagnostics.write_json(folder, "status.json", status_payload or {})
            return CheckinOutcome(
                RunStatus.NEED_RELOGIN,
                message="登入狀態已失效，請重新登入此帳號",
                detail={"url": page.url},
            )

        # --- 更新 session（token 續期後仍可重複使用） ---------------------
        await browser.update_state(account, context)
        diagnostics.write_json(folder, "status.json", status_payload or {})

        # today / today_status 已在登入判定階段由 API 取出，這裡直接重用。

        # --- 今日已簽到 ---------------------------------------------------
        if today_status == DayStatus.CLAIMED:
            return CheckinOutcome(
                RunStatus.ALREADY,
                points=_points_of(today),
                day_no=int(today.get("day_no") or 0),
                message="今日已簽到",
                detail={"today": today},
            )

        # --- 關閉可能擋住操作的彈窗（例如官方更新公告） -------------------
        await _dismiss_overlays(page, tag)

        # --- 等待簽到面板 -------------------------------------------------
        if not await _wait_panel(page, min(timeout_ms, 20000)):
            if today_status == DayStatus.AVAILABLE:
                return await _drift_outcome(page, folder, "簽到面板未出現（介面可能已改版）")
            if today_status is None:
                return await _drift_outcome(page, folder, "無法取得簽到狀態（介面可能已改版）")
            return CheckinOutcome(
                RunStatus.ALREADY,
                points=_points_of(today),
                message="今日已簽到（面板未顯示）",
                detail={"today": today},
            )

        if cancel is not None and cancel.is_set():
            return CheckinOutcome(RunStatus.FAILED, message="已取消")

        # --- 尋找並點擊簽到按鈕 -------------------------------------------
        match = await selectors.find_claim_button(page)
        if match is None:
            return await _drift_outcome(page, folder, "找不到簽到按鈕（介面可能已改版）")
        if match.looks_claimed:
            return CheckinOutcome(RunStatus.ALREADY, message="今日已簽到（按鈕顯示已領取）")

        logger.info(f"[{tag}] 找到簽到按鈕 → {match.selector}｜{match.label}")

        claim_payload, click_error = await _click_and_wait(page, match.locator, timeout_ms, tag)

        diagnostics.write_json(folder, "claim.json", claim_payload or {})
        await diagnostics.capture_page(page, folder, "after_claim")

        code = selectors.status_code_of(claim_payload)
        data = (claim_payload or {}).get("data") or {}
        if claim_payload is not None and code == 0 and int(data.get("claim_result") or 0) == 1:
            points = int(data.get("points") or 0)
            verified = await _verify_claimed(page)
            message = f"簽到成功，獲得 {points} 點"
            if not verified:
                message += "（未取得二次驗證）"
            logger.info(f"[{tag}] {message}")
            return CheckinOutcome(
                RunStatus.SUCCESS,
                points=points,
                day_no=int(data.get("day_no") or 0),
                message=message,
                detail={"claim": claim_payload, "verified": verified},
            )

        if claim_payload is not None:
            api_message = selectors.message_of(claim_payload) or f"API 回應碼 {code}"
            logger.warning(f"[{tag}] 簽到失敗：{api_message}")
            return CheckinOutcome(
                RunStatus.FAILED,
                message=f"簽到失敗：{api_message}",
                detail={"claim": claim_payload},
            )

        # 完全沒有 API 回應時，用 DOM 變化做最後判斷
        if not await selectors.panel_present(page):
            return CheckinOutcome(
                RunStatus.ALREADY, message="簽到後面板消失，判定為已簽到（未取得 API 回應）"
            )
        return CheckinOutcome(
            RunStatus.FAILED,
            message=click_error or "簽到未成功（未取得 API 回應）",
            detail={"selector": match.selector},
        )

    except PlaywrightError as exc:
        logger.warning(f"[{tag}] 執行錯誤：{exc}")
        return CheckinOutcome(RunStatus.FAILED, message=f"瀏覽器錯誤：{exc}")
    except Exception as exc:  # pragma: no cover - 保底
        logger.exception(f"[{tag}] 未預期錯誤")
        return CheckinOutcome(RunStatus.FAILED, message=f"未預期錯誤：{exc}")
    finally:
        if context is not None and not getattr(cfg, "keep_browser_open", False):
            try:
                await context.close()
            except Exception:
                pass
