"""診斷檔案：把簽到前後的 DOM / API 回應 / 截圖寫入資料夾，方便改版時更新選擇器。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app import paths


def _safe(text: str, limit: int = 40) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", text or "account")
    return cleaned[:limit] or "account"


def session_dir(tag: str = "") -> Path:
    """建立一次診斷資料夾：diagnostics/YYYYmmdd_HHMMSS_tag。"""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = paths.diagnostics_dir() / (f"{stamp}_{_safe(tag)}" if tag else stamp)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def write_json(folder: Path, name: str, data: Any) -> Path:
    path = folder / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    return path


async def capture_page(page, folder: Path, name: str = "page", screenshot: bool = True) -> None:
    """保存頁面 HTML 與（可選）截圖；失敗時不影響主流程。"""
    try:
        html = await page.content()
        (folder / f"{name}.html").write_text(html, "utf-8")
    except Exception:
        pass
    if not screenshot:
        return
    try:
        await page.screenshot(path=str(folder / f"{name}.png"), full_page=False)
    except Exception:
        pass


def prune(keep: int = 20) -> None:
    """只保留最近 N 個診斷資料夾。"""
    root = paths.diagnostics_dir()
    folders = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name)
    for folder in folders[:-max(1, keep)]:
        for child in sorted(folder.rglob("*"), reverse=True):
            try:
                child.unlink() if child.is_file() else child.rmdir()
            except OSError:
                pass
        try:
            folder.rmdir()
        except OSError:
            pass
