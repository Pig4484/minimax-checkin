"""路徑與資料存放規範測試（Roaming / Local 分流、可攜模式、舊版遷移）。"""

from __future__ import annotations

import pytest

from app import paths


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    """把 Roaming / Local 導向暫存目錄（模擬全新使用者的電腦）。"""
    roaming = tmp_path / "roaming" / "MinimaxCheckin"
    local = tmp_path / "local" / "MinimaxCheckin"
    monkeypatch.setattr(paths, "_roaming_base", lambda: roaming)
    monkeypatch.setattr(paths, "_local_base", lambda: local)
    monkeypatch.setattr(paths, "is_portable", lambda: False)
    return roaming, local


def test_config_lives_in_roaming(isolated):
    roaming, local = isolated
    assert paths.config_file() == roaming / "config.json"
    assert paths.config_file().parent != local


def test_runtime_data_lives_in_local(isolated):
    roaming, local = isolated
    for path in (
        paths.accounts_dir(),
        paths.logs_dir(),
        paths.diagnostics_dir(),
        paths.browsers_dir(),
        paths.state_file(),
    ):
        assert local in path.parents, f"{path} 應該位於 Local 而不是 Roaming"


def test_directories_are_created(isolated):
    assert paths.accounts_dir().is_dir()
    assert paths.logs_dir().is_dir()
    assert paths.diagnostics_dir().is_dir()
    assert paths.roaming_dir().is_dir()


def test_portable_mode_uses_install_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "is_portable", lambda: True)
    monkeypatch.setattr(paths, "install_dir", lambda: tmp_path / "app")
    assert paths.roaming_dir() == tmp_path / "app" / "data"
    assert paths.local_dir() == tmp_path / "app" / "data"


def test_portable_flag_detection(monkeypatch, tmp_path):
    (tmp_path / paths.PORTABLE_FLAG).write_text("", "utf-8")
    monkeypatch.delenv(paths.PORTABLE_ENV, raising=False)
    monkeypatch.setattr(paths, "install_dir", lambda: tmp_path)
    assert paths.is_portable() is True

    monkeypatch.setenv(paths.PORTABLE_ENV, "0")
    monkeypatch.setattr(paths, "install_dir", lambda: tmp_path / "absent")
    assert paths.is_portable() is False


def test_migrate_moves_legacy_runtime_data(isolated):
    roaming, local = isolated
    # 模擬舊版：所有東西都放在 Roaming
    (roaming / "accounts").mkdir(parents=True)
    (roaming / "accounts" / "abc.json").write_text("{}", "utf-8")
    (roaming / "logs").mkdir()
    (roaming / "logs" / "app.log").write_text("log", "utf-8")
    (roaming / "diagnostics").mkdir()
    (roaming / "state.json").write_text("{}", "utf-8")
    (roaming / "config.json").write_text("{}", "utf-8")
    (roaming / ".lock").write_text("", "utf-8")

    moved = paths.migrate_legacy()

    assert (local / "accounts" / "abc.json").exists()
    assert (local / "logs" / "app.log").exists()
    assert (local / "state.json").exists()
    assert not (roaming / "accounts").exists(), "舊目錄應該被清空"
    assert not (roaming / "logs").exists()
    assert (roaming / "config.json").exists(), "設定檔應留在 Roaming"
    assert not (roaming / ".lock").exists(), "舊鎖檔應被清除"
    assert any("accounts/abc.json" in item for item in moved)


def test_migrate_discards_duplicate_legacy_file(isolated):
    roaming, local = isolated
    (roaming / "state.json").parent.mkdir(parents=True, exist_ok=True)
    (roaming / "state.json").write_text('{"old":1}', "utf-8")
    (local).mkdir(parents=True, exist_ok=True)
    (local / "state.json").write_text('{"new":2}', "utf-8")

    moved = paths.migrate_legacy()

    assert (local / "state.json").read_text("utf-8") == '{"new":2}', "不應覆蓋新版資料"
    assert not (roaming / "state.json").exists()
    assert any("丟棄重複" in item for item in moved)


def test_migrate_is_noop_when_nothing_to_move(isolated):
    assert paths.migrate_legacy() == []