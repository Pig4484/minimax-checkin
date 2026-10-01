"""pytest 共用 fixture。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app import paths

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    path = FIXTURES / name
    if path.suffix == ".json":
        return json.loads(path.read_text("utf-8"))
    return path.read_text("utf-8")


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def panel_html() -> str:
    return load_fixture("signin_panel_available.html")


@pytest.fixture
def claimed_panel_html() -> str:
    return load_fixture("signin_panel_claimed.html")


@pytest.fixture
def modal_html() -> str:
    return load_fixture("blocking_modal.html")


@pytest.fixture
def status_available() -> dict:
    return load_fixture("signin_status_available.json")


@pytest.fixture
def status_claimed() -> dict:
    return load_fixture("signin_status_claimed.json")


@pytest.fixture
def claim_success() -> dict:
    return load_fixture("signin_claim_success.json")


@pytest.fixture
def temp_root(monkeypatch, tmp_path) -> Path:
    """把設定檔（Roaming）與本機資料（Local）都導向暫存目錄。"""
    roaming = tmp_path / "roaming" / "MinimaxCheckin"
    local = tmp_path / "local" / "MinimaxCheckin"
    monkeypatch.setattr(paths, "_roaming_base", lambda: roaming)
    monkeypatch.setattr(paths, "_local_base", lambda: local)
    monkeypatch.setattr(paths, "is_portable", lambda: False)
    return local


@pytest.fixture(scope="module")
def async_browser():
    """模組共用的 async Playwright 瀏覽器與事件迴圈。"""
    from playwright.async_api import async_playwright

    loop = asyncio.new_event_loop()

    async def start():
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch()
        return playwright, browser

    try:
        playwright, browser = loop.run_until_complete(start())
    except Exception as exc:  # pragma: no cover - 取決於環境
        loop.close()
        pytest.skip(f"無法啟動 Chromium（請先執行 playwright install chromium）：{exc}")

    yield loop, browser

    async def shutdown():
        await browser.close()
        await playwright.stop()

    loop.run_until_complete(shutdown())
    loop.close()
