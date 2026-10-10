"""帳號管理與 session 儲存測試。"""

from __future__ import annotations

import pytest

from app.core import crypto
from app.core.account import AccountManager, today_text

STATE = {
    "cookies": [
        {"name": "_token", "value": "jwt.token.value", "domain": ".minimax.io", "path": "/"}
    ],
    "origins": [
        {
            "origin": "https://agent.minimax.io",
            "localStorage": [{"name": "_token", "value": "jwt.token.value"}],
        }
    ],
}


def test_add_and_remove(temp_root):
    manager = AccountManager(encrypt=False)
    assert manager.accounts == []

    account = manager.add("測試帳號")
    assert manager.get(account.id) is account
    assert (temp_root / "accounts" / "index.json").exists()
    assert account.display_name == "測試帳號"

    manager.remove(account.id)
    assert manager.accounts == []
    assert not manager.has_state(account)


def test_display_name_fallbacks(temp_root):
    manager = AccountManager(encrypt=False)
    account = manager.add("")
    assert account.display_name.startswith("帳號 ")
    account.user_name = "呂俊傑"
    assert account.display_name == "呂俊傑"
    assert account.signed_in_today is False
    account.last_checkin_date = today_text()
    assert account.signed_in_today is True


def test_plain_session_roundtrip(temp_root):
    manager = AccountManager(encrypt=False)
    account = manager.add()
    manager.save_state(account, STATE)

    assert (temp_root / "accounts" / f"{account.id}.json").exists()
    assert manager.has_state(account)
    assert manager.load_state(account) == STATE
    assert account.last_login_at != ""


def test_encrypted_session_roundtrip(temp_root):
    if not crypto.is_available():
        pytest.skip("此環境沒有 pywin32（DPAPI）")

    manager = AccountManager(encrypt=True)
    account = manager.add()
    manager.save_state(account, STATE)

    path = temp_root / "accounts" / f"{account.id}.bin"
    assert path.exists()
    assert b"_token" not in path.read_bytes(), "session 內容不應以明文寫入"
    assert manager.load_state(account) == STATE


def test_update_and_summary(temp_root):
    manager = AccountManager(encrypt=False)
    first = manager.add("A")
    second = manager.add("B")
    manager.update(first.id, enabled=False)
    manager.update(
        second.id,
        last_checkin_date=today_text(),
        last_status="success",
        last_points=800,
        total_points=1600,
    )

    summary = manager.summary()
    assert summary["total"] == 2
    assert summary["enabled"] == 1
    assert summary["done_today"] == 1
    assert summary["points_today"] == 800
    assert summary["points_total"] == 1600


def test_move_reorders(temp_root):
    manager = AccountManager(encrypt=False)
    first = manager.add("A")
    manager.add("B")
    manager.move(first.id, 1)
    assert [a.display_name for a in manager.accounts] == ["B", "A"]


def test_auto_alias_skips_taken(temp_root):
    manager = AccountManager(encrypt=False)
    manager.add()  # 帳號 1
    manager.add("帳號 2")
    third = manager.add()
    assert third.alias == "帳號 3"
    assert len({a.alias for a in manager.accounts}) == 3


def test_rename_updates_alias(temp_root):
    """改名成功：別名被更新並寫回 index.json。"""
    manager = AccountManager(encrypt=False)
    account = manager.add("舊名")

    ok, reason = manager.rename(account.id, "新名字")
    assert ok is True, reason
    assert reason == ""
    assert manager.get(account.id).alias == "新名字"

    # 重新載入仍保留（確實 save 了）
    reloaded = AccountManager(encrypt=False)
    assert reloaded.get(account.id).alias == "新名字"

    # 前後空白會被去掉
    ok, reason = manager.rename(account.id, "  再改一次  ")
    assert ok is True, reason
    assert manager.get(account.id).alias == "再改一次"


def test_rename_rejects_blank(temp_root):
    """空白（或全空白）別名必須被擋下。"""
    manager = AccountManager(encrypt=False)
    account = manager.add("原名")

    for bad in ("", "   ", "\t\n"):
        ok, reason = manager.rename(account.id, bad)
        assert ok is False
        assert reason
    assert manager.get(account.id).alias == "原名"


def test_rename_rejects_too_long(temp_root):
    """超過 24 字必須被擋下，且剛好 24 字可通過。"""
    manager = AccountManager(encrypt=False)
    account = manager.add("原名")

    ok, reason = manager.rename(account.id, "x" * 25)
    assert ok is False
    assert reason

    ok, reason = manager.rename(account.id, "x" * 24)
    assert ok is True, reason


def test_rename_rejects_duplicate_alias(temp_root):
    """撞到其他帳號的別名必須被擋下；改成自己目前的別名應允許。"""
    manager = AccountManager(encrypt=False)
    first = manager.add("甲")
    second = manager.add("乙")

    ok, reason = manager.rename(second.id, "甲")
    assert ok is False
    assert "甲" in reason
    assert manager.get(second.id).alias == "乙"

    # 沿用自己現有名稱（視為無變更）不算撞名
    ok, reason = manager.rename(second.id, "乙")
    assert ok is True, reason


def test_rename_rejects_same_login_name(temp_root):
    """撞到其他帳號的 MiniMax user_name 必須被擋下（避免顯示混淆）。"""
    manager = AccountManager(encrypt=False)
    first = manager.add("甲")
    second = manager.add("乙")
    manager.update(first.id, user_name="呂俊傑")

    ok, reason = manager.rename(second.id, "呂俊傑")
    assert ok is False
    assert reason
    assert manager.get(second.id).alias == "乙"


def test_rename_missing_account(temp_root):
    """找不到帳號時回傳失敗與原因。"""
    manager = AccountManager(encrypt=False)
    ok, reason = manager.rename("does-not-exist", "新名字")
    assert ok is False
    assert reason


def test_corrupted_index_is_ignored(temp_root):
    index = temp_root / "accounts" / "index.json"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text("{ not json", "utf-8")
    assert AccountManager(encrypt=False).accounts == []
