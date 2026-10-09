"""簽到引擎：多帳號執行、結果彙總、改版（drift）偵測累計。"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from app.constants import RUN_STATUS_TEXT, SELECTOR_PACK_VERSION, RunStatus
from app.core import diagnostics
from app.core.account import Account, AccountManager, now_text, today_text
from app.core.checkin import CheckinOutcome, run_account_checkin
from app.core.state import RunStateStore
from app.logger import logger

Emit = Callable[[str, dict[str, Any]], None]


class CheckinEngine:
    """負責「跑一輪簽到」，並把每個帳號的結果寫回帳號資料。"""

    def __init__(
        self,
        cfg,
        accounts: AccountManager,
        browser,
        state: RunStateStore,
        emit: Emit | None = None,
    ) -> None:
        self.cfg = cfg
        self.accounts = accounts
        self.browser = browser
        self.state = state
        self._emit_fn = emit

    def emit(self, event: str, payload: dict[str, Any]) -> None:
        if self._emit_fn is not None:
            try:
                self._emit_fn(event, payload)
            except Exception:  # pragma: no cover - 不讓 UI 例外影響自動化
                pass

    # ------------------------------------------------------------------
    def drift_accounts(self) -> list[Account]:
        return [
            a for a in self.accounts.accounts if a.drift_count >= max(1, self.cfg.drift_threshold)
        ]

    async def run(
        self,
        reason: str = "manual",
        only_ids: list[str] | None = None,
        cancel: asyncio.Event | None = None,
    ) -> list[dict[str, Any]]:
        """執行一輪簽到，回傳每個帳號的結果清單。"""
        targets = [
            a
            for a in self.accounts.accounts
            if a.enabled and (only_ids is None or a.id in only_ids)
        ]
        if not targets:
            logger.warning("沒有可執行的帳號（請先新增並登入帳號）")
            return []

        # 與「互動登入」互斥：避免 headed/headless 互相把瀏覽器重啟而打斷對方
        lock = getattr(self.browser, "operation", None)
        if lock is None:
            return await self._run_targets(targets, reason, cancel)
        async with lock:
            return await self._run_targets(targets, reason, cancel)

    async def _run_targets(
        self,
        targets: list[Account],
        reason: str,
        cancel: asyncio.Event | None,
    ) -> list[dict[str, Any]]:
        logger.info(f"開始簽到（{reason}）：共 {len(targets)} 個帳號")
        self.emit("run_started", {"reason": reason, "total": len(targets)})

        semaphore = asyncio.Semaphore(max(1, int(self.cfg.concurrent_accounts)))
        results: list[dict[str, Any]] = []

        async def worker(account: Account) -> None:
            async with semaphore:
                if cancel is not None and cancel.is_set():
                    return
                self.emit(
                    "account_started",
                    {"account_id": account.id, "alias": account.display_name},
                )
                folder = diagnostics.session_dir(account.display_name)
                outcome = await run_account_checkin(
                    self.accounts,
                    self.browser,
                    account,
                    self.cfg,
                    diag_folder=folder,
                    cancel=cancel,
                )
                # 無頭模式失敗時，改用顯示視窗再試一次（可降低被風控擋下的機率）。
                # 注意：用副本 cfg 重試，不動共用的 self.cfg.headless，
                # 否則多帳號並行時會互相翻模式、打斷對方。
                if (
                    self.cfg.headless
                    and self.cfg.fallback_headed
                    and outcome.status in (RunStatus.FAILED, RunStatus.DRIFT)
                    and (cancel is None or not cancel.is_set())
                ):
                    logger.info(f"[{account.display_name}] 無頭模式未成功，改用顯示視窗重試")
                    import dataclasses

                    retry_cfg = dataclasses.replace(self.cfg, headless=False)
                    outcome = await run_account_checkin(
                        self.accounts,
                        self.browser,
                        account,
                        retry_cfg,
                        diag_folder=folder,
                        cancel=cancel,
                    )
                result = self._apply(account, outcome)
                results.append(result)
                self.emit("account_finished", result)

        await asyncio.gather(*(worker(account) for account in targets))
        self.accounts.save()

        ok_count = sum(1 for r in results if r["ok"])
        logger.info(f"簽到結束（{reason}）：{ok_count}/{len(results)} 成功")
        self.emit(
            "run_finished",
            {
                "reason": reason,
                "results": results,
                "ok": ok_count,
                "total": len(results),
                "drift_warning": bool(self.drift_accounts()),
            },
        )
        return results

    # ------------------------------------------------------------------
    def _apply(self, account: Account, outcome: CheckinOutcome) -> dict[str, Any]:
        """把結果寫回帳號資料並產生給 UI 的結果 dict。"""
        today = today_text()
        account.last_run_at = now_text()
        account.last_status = outcome.status.value
        account.last_message = outcome.message
        account.pack_version = SELECTOR_PACK_VERSION

        if outcome.status == RunStatus.SUCCESS:
            account.last_checkin_date = today
            account.last_points = outcome.points
            account.total_points += outcome.points
            account.drift_count = 0
        elif outcome.status == RunStatus.ALREADY:
            # 首次得知「今日已簽到」時，把今日點數計入累計（同一天重複執行不會重複計）
            if account.last_checkin_date != today and outcome.points > 0:
                account.total_points += outcome.points
            account.last_checkin_date = today
            account.last_points = outcome.points
            account.drift_count = 0
        elif outcome.status == RunStatus.DRIFT:
            account.drift_count += 1
            logger.warning(
                f"改版偵測：{account.display_name} 連續 {account.drift_count} 次找不到簽到介面"
            )
        elif outcome.status in (RunStatus.FAILED, RunStatus.RATE_LIMITED):
            account.last_points = 0

        self.accounts.update(account.id, persist=False)
        return {
            "account_id": account.id,
            "alias": account.display_name,
            "status": outcome.status.value,
            "status_text": RUN_STATUS_TEXT.get(outcome.status, outcome.status.value),
            "ok": outcome.ok,
            "points": outcome.points,
            "day_no": outcome.day_no,
            "message": outcome.message,
            "time": account.last_run_at,
        }
