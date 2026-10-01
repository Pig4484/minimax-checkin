"""API 回應解析測試（以實測擷取的 JSON fixture）。"""

from __future__ import annotations

from app.constants import DayStatus
from app.core import selectors


def test_today_entry_available(status_available):
    today = selectors.today_entry(status_available)
    assert today is not None
    assert today["day_no"] == 1
    assert today["status"] == DayStatus.AVAILABLE
    assert today["points"] == 800
    assert today["bonus_points"] == 400


def test_today_entry_claimed(status_claimed):
    today = selectors.today_entry(status_claimed)
    assert today is not None
    assert today["status"] == DayStatus.CLAIMED


def test_status_code_and_message(claim_success):
    assert selectors.status_code_of(claim_success) == 0
    assert selectors.message_of(claim_success) == "ok"
    assert claim_success["data"]["claim_result"] == 1
    assert claim_success["data"]["points"] == 800
    assert claim_success["data"]["day_no"] == 1


def test_status_helpers_handle_bad_input():
    assert selectors.today_entry(None) is None
    assert selectors.today_entry({}) is None
    assert selectors.today_entry({"data": {"days": [{"day_no": 1}]}}) is None
    assert selectors.status_code_of(None) is None
    assert selectors.message_of({}) == ""


def test_day_status_text():
    assert selectors.day_status_text(DayStatus.LOCKED) == "未解鎖"
    assert selectors.day_status_text(DayStatus.AVAILABLE) == "可簽到"
    assert selectors.day_status_text(DayStatus.CLAIMED) == "已領取"
    assert selectors.day_status_text(99).startswith("未知")
    assert selectors.day_status_text(None) == "未知"
