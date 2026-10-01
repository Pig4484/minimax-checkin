"""簽到引擎結果處理與排程時間計算測試。"""

from __future__ import annotations

import asyncio
from datetime import datetime

from app.config import AppConfig
from app.constants import RunStatus
from app.core.account import AccountManager, today_text
from app.core.checkin import CheckinOutcome
from app.core.engine import CheckinEngine
from app.core.scheduler import Scheduler
from app.core.state import RunStateStore


def make_engine(temp_root: object):
    cfg = AppConfig()
    accounts = AccountManager(encrypt=False)
    engine = CheckinEngine(cfg, accounts, None, RunStateStore())
    return cfg, accounts, engine


# --- 引擎：結果套用 --------------------------------------------------------
def test_success_records_points_and_date(temp_root):
    _, accounts, engine = make_engine(temp_root)
    account = accounts.add("A")

    row = engine._apply(
        account, CheckinOutcome(RunStatus.SUCCESS, points=800, day_no=1, message="簽到成功")
    )

    assert row["status"] == "success"
    assert row["ok"] is True
    assert row["status_text"] == "簽到成功"
    assert account.last_checkin_date == today_text()
    assert account.total_points == 800
    assert account.last_points == 800
    assert account.drift_count == 0


def test_already_does_not_accumulate_points(temp_root):
    """同一天先成功、再判定已簽到時，不應重複累計點數。"""
    _, accounts, engine = make_engine(temp_root)
    account = accounts.add("A")
    account.total_points = 800
    account.last_checkin_date = today_text()

    engine._apply(account, CheckinOutcome(RunStatus.ALREADY, points=800, message="今日已簽到"))

    assert account.last_checkin_date == today_text()
    assert account.total_points == 800, "已簽到不應重複累計點數"
    assert account.last_points == 800


def test_already_counts_once_when_first_seen_today(temp_root):
    """若程式今天第一次執行就發現「已簽到」（例如先前手動簽），點數仍計入累計一次。"""
    _, accounts, engine = make_engine(temp_root)
    account = accounts.add("A")

    engine._apply(account, CheckinOutcome(RunStatus.ALREADY, points=800, message="今日已簽到"))
    assert account.total_points == 800

    engine._apply(account, CheckinOutcome(RunStatus.ALREADY, points=800, message="今日已簽到"))
    assert account.total_points == 800, "第二次執行不應再累加"


def test_drift_increases_counter_until_threshold(temp_root):
    cfg, accounts, engine = make_engine(temp_root)
    account = accounts.add("A")
    cfg.drift_threshold = 2

    for _ in range(2):
        engine._apply(account, CheckinOutcome(RunStatus.DRIFT, message="找不到按鈕"))

    assert account.drift_count == 2
    assert [a.id for a in engine.drift_accounts()] == [account.id]

    engine._apply(account, CheckinOutcome(RunStatus.SUCCESS, points=800))
    assert account.drift_count == 0, "成功後應清除改版計數"
    assert engine.drift_accounts() == []


def test_need_relogin_keeps_status(temp_root):
    _, accounts, engine = make_engine(temp_root)
    account = accounts.add("A")

    row = engine._apply(
        account, CheckinOutcome(RunStatus.NEED_RELOGIN, message="登入狀態已失效")
    )

    assert row["ok"] is False
    assert row["status"] == "need_relogin"
    assert account.last_checkin_date == ""
    assert account.last_message == "登入狀態已失效"


def test_run_without_accounts_returns_empty(temp_root):
    _, _, engine = make_engine(temp_root)
    assert asyncio.run(engine.run("manual")) == []


# --- 排程：時間計算 --------------------------------------------------------
def make_scheduler(cfg: AppConfig) -> Scheduler:
    return Scheduler(cfg, None, None, None)


def test_today_target_uses_configured_time():
    cfg = AppConfig()
    cfg.jitter_minutes = 0
    cfg.daily_time = "09:00"
    scheduler = make_scheduler(cfg)
    now = datetime(2026, 9, 28, 7, 0)
    assert scheduler.today_target(now) == datetime(2026, 9, 28, 9, 0)


def test_next_run_rolls_to_tomorrow_when_passed():
    cfg = AppConfig()
    cfg.jitter_minutes = 0
    cfg.daily_time = "09:00"
    scheduler = make_scheduler(cfg)
    now = datetime(2026, 9, 28, 10, 0)
    target = scheduler.next_run_at(now)
    assert target == datetime(2026, 9, 29, 9, 0)


def test_next_run_keeps_today_when_upcoming():
    cfg = AppConfig()
    cfg.jitter_minutes = 0
    cfg.daily_time = "09:00"
    scheduler = make_scheduler(cfg)
    now = datetime(2026, 9, 28, 8, 0)
    assert scheduler.next_run_at(now) == datetime(2026, 9, 28, 9, 0)


def test_jitter_shift_is_bounded():
    cfg = AppConfig()
    cfg.daily_time = "12:00"
    cfg.jitter_minutes = 15
    scheduler = make_scheduler(cfg)
    now = datetime(2026, 9, 28, 0, 0)
    target = scheduler.today_target(now)
    assert datetime(2026, 9, 28, 11, 45) <= target <= datetime(2026, 9, 28, 12, 15)


def test_next_run_label_is_human_readable():
    cfg = AppConfig()
    cfg.jitter_minutes = 0
    scheduler = make_scheduler(cfg)
    label = scheduler.next_run_label()
    assert "後" in label or label == "即將執行"


# --- 執行狀態 --------------------------------------------------------------
def test_state_store_tracks_attempts(temp_root):
    store = RunStateStore()
    store.mark_attempt("scheduled")
    assert store.ran_today is True
    assert store.state.attempts == 1

    store.mark_finished(False, "0/1 成功")
    assert store.state.all_ok is False
    assert store.last_attempt_datetime is not None
