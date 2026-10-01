"""以 Windows DPAPI 加密保護登入 session（綁定當前 Windows 使用者）。

若 pywin32 不可用，會自動退回明文 JSON，並在設定頁提示風險。
"""

from __future__ import annotations

import json
from typing import Any

try:  # pragma: no cover - 取決於執行環境
    import win32crypt

    _AVAILABLE = True
except Exception:  # pragma: no cover
    win32crypt = None  # type: ignore[assignment]
    _AVAILABLE = False

_DESCRIPTION = "MinimaxCheckin login session"


def is_available() -> bool:
    return _AVAILABLE


def protect(data: bytes) -> bytes:
    """以 DPAPI 加密（僅當前使用者可解密）。"""
    if not _AVAILABLE:
        raise RuntimeError("DPAPI 無法使用（缺少 pywin32）")
    blob = win32crypt.CryptProtectData(data, _DESCRIPTION, None, None, None, 0)
    if isinstance(blob, tuple):  # 部分 pywin32 版本回傳 (blob, description)
        blob = blob[0]
    return bytes(blob)


def unprotect(blob: bytes) -> bytes:
    """解密 DPAPI 資料。"""
    if not _AVAILABLE:
        raise RuntimeError("DPAPI 無法使用（缺少 pywin32）")
    data = win32crypt.CryptUnprotectData(blob, None, None, None, 0)
    if isinstance(data, tuple):
        data = data[1]
    return bytes(data)


def dumps_state(state: dict[str, Any], encrypt: bool = True) -> tuple[bytes, bool]:
    """序列化 storage_state；回傳 (資料, 是否已加密)。"""
    payload = json.dumps(state, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if encrypt and is_available():
        return protect(payload), True
    return payload, False


def loads_state(raw: bytes, encrypted: bool) -> dict[str, Any]:
    if encrypted:
        raw = unprotect(raw)
    return json.loads(raw.decode("utf-8"))
