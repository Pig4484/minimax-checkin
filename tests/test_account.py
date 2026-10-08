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


def test_corrupted_index_is_ignored(temp_root):
    index = temp_root / "accounts" / "index.json"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text("{ not json", "utf-8")
    assert AccountManager(encrypt=False).accounts == []
