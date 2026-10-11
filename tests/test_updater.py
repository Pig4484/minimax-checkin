"""應用更新檢查測試：版號比較＋API 解析。"""

from __future__ import annotations

from app.core import updater
from app.core.updater import UpdateInfo


def test_parse_version_basic():
    assert updater.parse_version("v1.0.10") == (1, 0, 10)
    assert updater.parse_version("1.0") == (1, 0)
    assert updater.parse_version("") == ()


def test_is_newer_traps():
    assert updater.is_newer("1.0.10", "1.0.9") is True
    assert updater.is_newer("1.0.9", "1.0.10") is False
    assert updater.is_newer("1.0", "1.0.0") is False
    assert updater.is_newer("", "1.0.0") is False
    assert updater.is_newer("1.0.1", "1.0.1") is False


def test_fetch_latest_parses_tag(monkeypatch):
    import io
    import json

    payload = {"tag_name": "v9.9.9", "html_url": "https://example.invalid/r"}

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda req, timeout=15.0: FakeResp())
    info = updater.fetch_latest()
    assert isinstance(info, UpdateInfo)
    assert info.checked is True
    assert info.latest == "9.9.9"
    assert info.url == "https://example.invalid/r"


def test_fetch_latest_failure_returns_checked(monkeypatch):
    def boom(req, timeout=15.0):
        raise OSError("offline")

    monkeypatch.setattr(updater.urllib.request, "urlopen", boom)
    info = updater.fetch_latest()
    assert info.checked is True
    assert info.has_update is False
    assert info.error
