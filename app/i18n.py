"""介面語言：繁中／簡中／英文三語（安裝時跟隨系統語言，可於設定頁切換）。

業界做法說明：專業軟體（Chrome／VS Code 類）不是「自動翻譯」，
而是維護一份「字串表」（每種語言一份 key→文字對照）。
本專案採用務實做法：UI 顯示文字走 `t(key)` 查表，
日誌／診斷檔維持繁中（開發者閱讀用，不進翻譯表）。
"""

from __future__ import annotations

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


def _register(lang: str, table: dict[str, str]) -> None:
    _STRINGS[lang] = dict(table)


# --- 繁體中文（預設，與現有 UI 文案一致） -----------------------------------
_register(LANG_ZH_TW, {
    "nav.overview": "總覽",
    "nav.accounts": "帳號",
    "nav.logs": "紀錄",
    "nav.settings": "設定",
    "nav.run_now": "立即簽到",
    "nav.run_now.tooltip": "立即執行一次簽到",
    "search.settings": "搜尋設定",
    "tray.show": "顯示主視窗",
    "tray.results": "今日結果",
    "tray.open_data": "開啟資料目錄",
    "tray.quit": "結束",
    "tray.tooltip": "｜每日自動簽到",
    "tray.still_running.title": "仍在背景執行",
    "tray.still_running.body": "程式已縮到系統匣，會依排程自動簽到。",
    "tray.still_running.ok": "知道了",
    "tray.still_running.never": "不再顯示此提示",
})

# --- 簡體中文 --------------------------------------------------------------
_register(LANG_ZH_CN, {
    "nav.overview": "总览",
    "nav.accounts": "账号",
    "nav.logs": "记录",
    "nav.settings": "设置",
    "nav.run_now": "立即签到",
    "nav.run_now.tooltip": "立即执行一次签到",
    "search.settings": "搜索设置",
    "tray.show": "显示主窗口",
    "tray.results": "今日结果",
    "tray.open_data": "打开数据目录",
    "tray.quit": "退出",
    "tray.tooltip": "｜每日自动签到",
    "tray.still_running.title": "仍在后台运行",
    "tray.still_running.body": "程序已缩到系统托盘，会按排程自动签到。",
    "tray.still_running.ok": "知道了",
    "tray.still_running.never": "不再显示此提示",
})

# --- English ---------------------------------------------------------------
_register(LANG_EN, {
    "nav.overview": "Overview",
    "nav.accounts": "Accounts",
    "nav.logs": "Logs",
    "nav.settings": "Settings",
    "nav.run_now": "Check in now",
    "nav.run_now.tooltip": "Run a check-in immediately",
    "search.settings": "Search settings",
    "tray.show": "Show main window",
    "tray.results": "Today's results",
    "tray.open_data": "Open data folder",
    "tray.quit": "Quit",
    "tray.tooltip": " | Daily auto check-in",
    "tray.still_running.title": "Still running in background",
    "tray.still_running.body": "The app is minimized to the tray and will check in on schedule.",
    "tray.still_running.ok": "Got it",
    "tray.still_running.never": "Don't show this again",
})


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


def t(key: str, **kwargs: Any) -> str:
    """取目前語言的字串；缺 key 時退回繁中，再缺則回傳 key 本身。"""
    table = _STRINGS.get(_current, {})
    text = table.get(key)
    if text is None:
        text = _STRINGS[LANG_ZH_TW].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
