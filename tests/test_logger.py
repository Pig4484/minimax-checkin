"""日誌模組測試（含打包版視窗化模式：sys.stderr 為 None 的情境）。"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

from app import logger as app_logger


def _flush() -> None:
    """loguru 使用 enqueue=True（非同步），斷言前需等待寫入完成。"""
    try:
        app_logger.logger.complete()
    except Exception:
        pass


def _log_file(root) -> Path:
    stamp = datetime.now().strftime("%Y%m%d")
    return root / "logs" / f"app_{stamp}.log"


def test_setup_skips_console_when_streams_are_none(monkeypatch, temp_root):
    """PyInstaller 視窗化模式（console=False）下 sys.stderr/stdout 為 None，
    必須略過主控台 sink，否則 loguru 會拋 TypeError 使程式無聲結束。"""
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setattr(sys, "stdout", None)

    app_logger.setup("INFO", 7)  # 不應拋出例外
    app_logger.logger.info("測試訊息")
    _flush()

    log_file = _log_file(temp_root)
    assert log_file.exists(), "即使沒有主控台，仍應寫入日誌檔"
    assert "測試訊息" in log_file.read_text("utf-8")
    app_logger.logger.remove()


def test_setup_writes_to_file(temp_root):
    app_logger.setup("DEBUG", 7)
    app_logger.logger.debug("檔案測試")
    _flush()

    log_file = _log_file(temp_root)
    assert log_file.exists()
    assert "檔案測試" in log_file.read_text("utf-8")
    app_logger.logger.remove()


def test_gui_sink_receives_lines(temp_root):
    received: list[str] = []
    app_logger.setup("DEBUG", 7, gui_sink=received.append)
    app_logger.logger.info("給介面的訊息")
    _flush()
    assert any("給介面的訊息" in line for line in received)
    assert all(line.count("|") >= 2 for line in received), "格式應為 LEVEL|時間|訊息"
    app_logger.logger.remove()


def test_set_level_without_console_is_safe(monkeypatch, temp_root):
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setattr(sys, "stdout", None)
    app_logger.set_level("ERROR")  # 不應拋出例外


def test_crash_handler_writes_file(temp_root):
    app_logger.setup("INFO", 7)
    captured: list[tuple[str, object]] = []
    app_logger.install_crash_handler(lambda message, path: captured.append((message, path)))

    try:
        raise ValueError("測試用錯誤")
    except ValueError:
        sys.excepthook(*sys.exc_info())

    crash_log = temp_root / "logs" / "crash.log"
    assert crash_log.exists()
    content = crash_log.read_text("utf-8")
    assert "測試用錯誤" in content
    assert "Traceback" in content
    assert captured and "測試用錯誤" in captured[0][0]

    sys.excepthook = sys.__excepthook__  # 還原，避免影響其他測試


def test_crash_handler_ignores_keyboard_interrupt(temp_root):
    app_logger.setup("INFO", 7)
    app_logger.install_crash_handler(None)
    try:
        raise KeyboardInterrupt()
    except KeyboardInterrupt:
        sys.excepthook(*sys.exc_info())
    assert not (temp_root / "logs" / "crash.log").exists()
    sys.excepthook = sys.__excepthook__