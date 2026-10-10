"""介面語言測試：三語字串表＋系統語言偵測。"""

from __future__ import annotations

import json
from pathlib import Path

from app import i18n
from app.i18n import LANG_EN, LANG_ZH_CN, LANG_ZH_TW, detect_system_language, set_language, t


def test_all_languages_cover_nav_keys():
    keys = [
        "nav.overview", "nav.accounts", "nav.logs", "nav.settings",
        "nav.run_now", "search.settings", "tray.show", "tray.quit",
        "tray.still_running.title", "tray.still_running.never",
    ]
    for lang in (LANG_ZH_TW, LANG_ZH_CN, LANG_EN):
        set_language(lang)
        for key in keys:
            text = t(key)
            assert text and text != key, f"{lang}:{key} 缺翻譯"
    set_language(LANG_ZH_TW)


def test_unknown_language_falls_back_to_traditional():
    set_language("ja")
    assert i18n.current_language() == LANG_ZH_TW
    assert t("nav.overview") == "總覽"


def test_detect_system_language_returns_supported():
    assert detect_system_language() in (LANG_ZH_TW, LANG_ZH_CN, LANG_EN)


def test_locale_files_are_complete():
    root = Path(__file__).parent.parent / "app" / "locales"
    tw = json.loads((root / "zh-TW.json").read_text("utf-8"))
    assert len(tw) >= 200, f"繁中表應至少 200 key，實際 {len(tw)}"
    for name in ("zh-CN", "en"):
        other = json.loads((root / f"{name}.json").read_text("utf-8"))
        missing = sorted(set(tw) - set(other))
        assert not missing, f"{name} 缺 key：{missing[:10]}"
        empty = sorted(k for k in tw if not str(other.get(k, "")).strip())
        assert not empty, f"{name} 有空翻譯：{empty[:10]}"
