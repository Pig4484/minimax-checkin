"""應用更新檢查：對照 GitHub Releases 的最新版號。

設計（提示式更新，不做靜默自動安裝）：
- 公開 API，無需登入／token：GET .../releases/latest
- 每天最多查一次（成功或失敗都記錄時間，避免每次排程都打 API）
- 有新版 → 發 `update_available` 事件，GUI 顯示 InfoBar＋托盤通知，
  點擊開啟 releases 頁面讓使用者自行下載安裝（覆蓋安裝即可，
  設定與帳號在 AppData，不會遺失）
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.constants import APP_VERSION

OWNER = "Pig4484"
REPO = "minimax-checkin"
API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{OWNER}/{REPO}/releases"


@dataclass
class UpdateInfo:
    """更新檢查結果。"""

    checked: bool = False       # 本次是否有執行檢查（含失敗）
    has_update: bool = False    # 是否有新版
    latest: str = ""            # 遠端最新版號（不含 v 前綴，如 1.0.1）
    url: str = ""               # 下載頁面（releases 頁）
    error: str = ""             # 失敗原因（給日誌，不一定顯示給使用者）


def parse_version(text: str) -> tuple[int, ...]:
    """把版號字串轉成可比較的 tuple（容錯：取前導數字段）。

    "v1.0.10" → (1, 0, 10)；"1.0" → (1, 0)；"abc" → ()。
    """
    parts: list[int] = []
    cleaned = (text or "").strip().lstrip("vV")
    for chunk in cleaned.split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        if not digits and chunk != "0":
            # 遇到 "1rc1" 取 1；纯非数字段则停止
            if not parts and not digits:
                continue
            break
        try:
            parts.append(int(digits or 0))
        except ValueError:
            break
    return tuple(parts)


def is_newer(remote: str, local: str = APP_VERSION) -> bool:
    """遠端版號是否比本地新（空遠端一律視為無更新）。"""
    r, l = parse_version(remote), parse_version(local)
    if not r or not l:
        return False
    # 補齊長度再比較（1.0 vs 1.0.0 視為相等）
    width = max(len(r), len(l))
    r += (0,) * (width - len(r))
    l += (0,) * (width - len(l))
    return r > l


def fetch_latest(timeout: float = 15.0) -> UpdateInfo:
    """查詢 GitHub 最新 release；任何失敗都回傳 checked=False，不拋例外。"""
    try:
        req = urllib.request.Request(
            API_URL,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "minimax-checkin"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return UpdateInfo(checked=True, error=f"{type(exc).__name__}: {exc}")
    tag = str(data.get("tag_name") or "")
    version = tag.lstrip("vV")
    url = str(data.get("html_url") or RELEASES_PAGE)
    if not version:
        return UpdateInfo(checked=True, error="遠端回應缺少 tag_name")
    return UpdateInfo(
        checked=True,
        has_update=is_newer(version),
        latest=version,
        url=url,
    )


def today_text() -> str:
    return datetime.now().strftime("%Y-%m-%d")
