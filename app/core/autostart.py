"""Windows 開機自啓動（HKCU\\...\\Run，免管理員權限）。"""

from __future__ import annotations

import sys

try:
    import winreg
except ImportError:  # pragma: no cover - 非 Windows
    winreg = None  # type: ignore[assignment]

from app import paths
from app.logger import logger

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "MinimaxCheckin"


def is_supported() -> bool:
    return winreg is not None


def _read() -> str | None:
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return str(value)
    except FileNotFoundError:
        return None
    except OSError:
        return None


def is_enabled() -> bool:
    return _read() is not None


def current_command() -> str | None:
    return _read()


def enable() -> bool:
    """寫入登錄檔；成功回傳 True。"""
    if winreg is None:
        return False
    command = paths.launch_command()
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
        logger.info(f"已啟用開機自啓動：{command}")
        return True
    except OSError as exc:
        logger.warning(f"設定開機自啓動失敗：{exc}")
        return False


def disable() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_WRITE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
        logger.info("已關閉開機自啓動")
        return True
    except FileNotFoundError:
        return True
    except OSError as exc:
        logger.warning(f"移除開機自啓動失敗：{exc}")
        return False


def apply(enabled: bool) -> bool:
    return enable() if enabled else disable()


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))
