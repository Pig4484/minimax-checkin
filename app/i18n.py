"""介面語言：繁中／簡中／英文三語（安裝時跟隨系統語言，可於設定頁切換）。

業界做法說明：專業軟體（Chrome／VS Code 類）不是「自動翻譯」，
而是維護一份「字串表」（每種語言一份 key→文字對照）。
本專案做法：UI 顯示文字走 `t(key)` 查 `app/locales/*.json`，
日誌／診斷檔維持繁中（開發者閱讀用，不進翻譯表）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LANG_ZH_TW = "zh-TW"  # 繁體中文（預設）
LANG_ZH_CN = "zh-CN"  # 簡體中文
LANG_EN = "en"        # English

LANGUAGE_CHOICES = (LANG_ZH_TW, LANG_ZH_CN, LANG_EN)
LANGUAGE_LABELS = {
    LANG_ZH_TW: "繁體中文",
    LANG_ZH_CN: "简体中文",
    LANG_EN: "English",
}

_current: str = LANG_ZH_TW

_STRINGS: dict[str, dict[str, str]] = {}


def _locales_dir() -> Path:
    import sys

    base = getattr(sys, "_MEIPASS", None)
    if base:
        bundled = Path(base) / "app" / "locales"
        if bundled.is_dir():
            return bundled
    return Path(__file__).resolve().parent / "locales"


def _load(lang: str) -> dict[str, str]:
    if lang in _STRINGS:
        return _STRINGS[lang]
    path = _locales_dir() / f"{lang}.json"
    try:
        table = json.loads(path.read_text("utf-8"))
    except Exception:
        table = {}
    _STRINGS[lang] = {str(k): str(v) for k, v in table.items()}
    return _STRINGS[lang]


def t(key: str, **kwargs: Any) -> str:
    """取目前語言的字串；缺 key 時退回繁中，再缺則回傳 key 本身。"""
    text = _load(_current).get(key)
    if text is None:
        text = _load(LANG_ZH_TW).get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def available_keys() -> set[str]:
    """繁中表的全部 key（翻譯完整度檢查用）。"""
    return set(_load(LANG_ZH_TW))


def detect_system_language() -> str:
    """安裝時跟隨系統語言：zh-CN→簡中，en開頭→英文，其餘→繁中。"""
    try:
        from PySide6.QtCore import QLocale

        name = QLocale.system().name().lower().replace("-", "_")
    except Exception:
        name = ""
    if name.startswith("zh_cn") or name.startswith("zh_sg") or name.startswith("zh_hans"):
        return LANG_ZH_CN
    if name.startswith("en"):
        return LANG_EN
    return LANG_ZH_TW


def set_language(lang: str) -> str:
    """切換目前語言；未知值退回繁中。回傳實際生效的語言。"""
    global _current
    _current = lang if lang in LANGUAGE_CHOICES else LANG_ZH_TW
    return _current


def current_language() -> str:
    return _current
