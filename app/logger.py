"""日誌設定（loguru）：檔案輪替 + 可選的 GUI 即時輸出 sink。

GUI sink 會收到字串：``LEVEL|HH:mm:ss|訊息``（以 ``|`` 分隔，最多切三段）。
"""

from __future__ import annotations

import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable

from loguru import logger

from app import paths

_FORMAT = "{level}|{time:HH:mm:ss}|{message}"
_configured = False


def enable_utf8_console() -> None:
    """讓命令列工具的輸出（含重導向）使用 UTF-8，避免 Windows 主控台中文亂碼。"""
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except Exception:
            pass


def _has_console() -> bool:
    """是否有可用的主控台輸出。

    PyInstaller 的視窗化模式（console=False）下 ``sys.stderr`` / ``sys.stdout`` 會是
    ``None``，此時若仍嘗試建立主控台 sink，loguru 會拋 ``TypeError`` 導致程式無聲結束。
    """
    return sys.stderr is not None or sys.stdout is not None


def setup(level: str = "INFO", keep_days: int = 30, gui_sink: Callable[[str], None] | None = None):
    """初始化 loguru（重複呼叫只會更新 sink）。"""
    global _configured
    logger.remove()
    if _has_console():
        logger.add(
            sys.stderr or sys.stdout,
            level=level,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}",
            colorize=True,
        )
    logger.add(
        paths.logs_dir() / "app_{time:YYYYMMDD}.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <7} | {name}:{line} | {message}",
        rotation="00:00",
        retention=f"{max(1, int(keep_days))} days",
        encoding="utf-8",
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )
    if gui_sink is not None:
        logger.add(gui_sink, level="DEBUG", format=_FORMAT)
    _configured = True
    return logger


def set_level(level: str) -> None:
    """調整主控台 sink 的等級（檔案 sink 固定 DEBUG 以便除錯）。"""
    if not _has_console():
        return
    try:
        logger.remove(0)
    except Exception:
        pass
    logger.add(
        sys.stderr or sys.stdout,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}",
        colorize=True,
    )


def _write_crash(text: str) -> Path | None:
    """把未預期錯誤寫入 crash.log（不依賴 loguru，確保一定寫得出來）。"""
    try:
        path = paths.logs_dir() / "crash.log"
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n===== {stamp} =====\n{text}\n")
        return path
    except Exception:
        return None


def install_crash_handler(on_error: Callable[[str, Path | None], None] | None = None) -> None:
    """攔截未處理例外：寫入 crash.log，並可回呼讓 GUI 顯示錯誤視窗。"""

    def handle(exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            return
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        path = _write_crash(text)
        try:
            logger.error(f"未預期錯誤：{exc_value}")
        except Exception:
            pass
        if on_error is not None:
            try:
                on_error(str(exc_value), path)
            except Exception:
                pass

    sys.excepthook = handle

    def thread_handle(args) -> None:
        handle(args.exc_type, args.exc_value, args.exc_traceback)

    try:
        threading.excepthook = thread_handle  # type: ignore[assignment]
    except Exception:
        pass


def get(*names: str) -> str:
    return " | ".join(n for n in names if n)


__all__ = [
    "logger",
    "setup",
    "set_level",
    "enable_utf8_console",
    "install_crash_handler",
    "get",
]
