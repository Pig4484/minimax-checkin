"""排程器：每日固定時間（含隨機抖動）、啟動補簽、當日失敗重試。

設計：所有執行都排入單一佇列並由同一個迴圈執行，因此不會有兩輪簽到同時跑。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Callable

from app.core.account import AccountManager
from app.core.engine import CheckinEngine
from app.core.state import RunStateStore
from app.i18n import t
from app.logger import logger

TIME_FORMAT = "%Y-%m-%d %H:%M"


class Scheduler:
    def __init__(
        self,
        cfg,
        engine: CheckinEngine,
        accounts: AccountManager,
        state: RunStateStore,
        emit: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.cfg = cfg
        self.engine = engine
        self.accounts = accounts
        self.state = state
        self._emit_fn = emit
        self._stop = asyncio.Event()
        self._queue: asyncio.Queue[tuple[str, list[str] | None]] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._startup_checked = False
        self._cancel = asyncio.Event()
        self.running = False
        self.current_reason = ""

    # ------------------------------------------------------------------
    def emit(self, event: str, payload: dict[str, Any]) -> None:
        if self._emit_fn is not None:
            try:
                self._emit_fn(event, payload)
            except Exception:  # pragma: no cover
                pass

    # --- 時間計算 ------------------------------------------------------
    def today_target(self, moment: datetime | None = None) -> datetime:
        """指定日期當天的目標執行時間（以日期為隨機抖動種子，當天固定）。"""
        moment = moment or datetime.now()
        hour, minute = self.cfg.daily_time_obj.hour, self.cfg.daily_time_obj.minute
        base = moment.replace(hour=hour, minute=minute, second=0, microsecond=0)
        jitter = self.cfg.daily_jitter_minutes(moment.strftime("%Y-%m-%d"))
        return base + timedelta(minutes=jitter)

    def next_run_at(self, now: datetime | None = None) -> datetime:
        """下一次排程執行時間（今日已過則為明日）。"""
        now = now or datetime.now()
        target = self.today_target(now)
        if target <= now:
            target = self.today_target(now + timedelta(days=1))
        return target

    def next_run_text(self) -> str:
        return self.next_run_at().strftime(TIME_FORMAT)

    def next_run_label(self) -> str:
        target = self.next_run_at()
        delta = target - datetime.now()
        if delta.total_seconds() < 60:
            return t("scheduler.soon")
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes = remainder // 60
        if hours:
            return t("scheduler.hours", hours=hours, minutes=minutes)
        return t("scheduler.minutes", minutes=minutes)

    # --- 生命週期 ------------------------------------------------------
    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.ensure_future(self._loop())
            logger.info(f"排程器已啟動，下次執行：{self.next_run_text()}")

    async def stop(self) -> None:
        self._stop.set()
        self._cancel.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=10)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
        logger.info("排程器已停止")

    async def trigger(self, reason: str = "manual", only_ids: list[str] | None = None) -> None:
        """排入一次執行請求（GUI 按鈕或排程器本身呼叫）。"""
        await self._queue.put((reason, only_ids))

    def cancel_current(self) -> None:
        self._cancel.set()

    # --- 主迴圈 --------------------------------------------------------
    async def _loop(self) -> None:
        await asyncio.sleep(3)
        while not self._stop.is_set():
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - 保底
                logger.warning(f"排程器錯誤：{exc}")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass

    def _pending_accounts(self) -> list:
        """尚未完成今日簽到的帳號（需要重新登入者當日不再重試）。"""
        today = datetime.now().strftime("%Y-%m-%d")
        pending = []
        for account in self.accounts.enabled_accounts():
            if account.signed_in_today:
                continue
            if account.last_status == "need_relogin" and account.last_run_at.startswith(today):
                continue
            pending.append(account)
        return pending

    async def _tick(self) -> None:
        # 1) 外部觸發（手動立即簽到）
        while not self._queue.empty():
            reason, ids = self._queue.get_nowait()
            await self._run(reason, ids)

        now = datetime.now()
        self.state.reset_for_today()

        # 2) 啟動補簽（每個行程只檢查一次）
        if not self._startup_checked:
            self._startup_checked = True
            if self.cfg.run_on_start_if_missed and self._pending_accounts():
                logger.info("啟動補簽：今日仍有帳號未簽到")
                await self._run("startup")

        # 3) 每日排程（若今日已無待簽帳號，直接標記完成，避免空跑）
        if not self.state.ran_today and now >= self.today_target(now):
            if self._pending_accounts():
                await self._run("scheduled")
            else:
                self.state.mark_finished(True, "今日已完成，無需執行")

        # 4) 當日失敗重試
        last_attempt = self.state.last_attempt_datetime
        if (
            self.state.ran_today
            and not self.state.state.all_ok
            and self.state.state.attempts <= max(0, self.cfg.retry_times)
            and last_attempt is not None
            and now >= last_attempt + timedelta(minutes=self.cfg.retry_interval_minutes)
            and self._pending_accounts()
        ):
            await self._run("retry")

    async def _run(self, reason: str, ids: list[str] | None = None) -> None:
        self.running = True
        self.current_reason = reason
        self._cancel = asyncio.Event()
        self.state.mark_attempt(reason)
        self.emit("run_state", {"running": True, "reason": reason})
        results: list[dict[str, Any]] = []
        try:
            results = await self.engine.run(reason=reason, only_ids=ids, cancel=self._cancel)
        finally:
            self.running = False
            self.current_reason = ""
        ok = bool(results) and all(r["ok"] for r in results)
        done = sum(1 for r in results if r["ok"])
        self.state.mark_finished(ok, f"{done}/{len(results)} 成功")
        self.emit("run_state", {"running": False, "reason": reason, "next_run_text": self.next_run_text()})
