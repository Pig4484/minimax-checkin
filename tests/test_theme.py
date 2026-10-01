"""介面主題測試：淺色／深色模式必須正確反映在內容區與卡片。

背景：Qt 6.8+ 的 `QStyleHints.colorScheme()` 預設跟隨 Windows 系統設定；
若 App 選淺色但系統是深色，使用原生調色盤繪製的頁面會變成深色，
出現「標題列是淺色、內容區是深色」的詭異外觀。
"""

from __future__ import annotations

import pytest

from app.ui.components import make_background_transparent, sync_qt_color_scheme


def _qt_app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_sync_qt_color_scheme_matches_app_theme(monkeypatch):
    """App 主題為淺色時，Qt 的 colorScheme 必須是 Light（不受系統深色影響）。"""
    app = _qt_app()
    from PySide6.QtCore import Qt
    from qfluentwidgets import Theme, setTheme

    for theme, expected in ((Theme.LIGHT, Qt.ColorScheme.Light),
                            (Theme.DARK, Qt.ColorScheme.Dark)):
        setTheme(theme)
        sync_qt_color_scheme()
        assert app.styleHints().colorScheme() == expected


def test_make_background_transparent_uses_theme_color():
    """頁面與 viewport 必須套用「當前主題的實色背景」，不可依賴系統配色或透出底層材質。"""
    from PySide6.QtWidgets import QWidget

    from qfluentwidgets import Theme, isDarkTheme, setTheme

    _qt_app()
    for theme, expected in ((Theme.DARK, "#1c1c1c"), (Theme.LIGHT, "#f3f3f3")):
        setTheme(theme)
        widget = QWidget()
        make_background_transparent(widget)
        style = widget.styleSheet()
        assert expected in style.lower(), f"{theme} 應使用 {expected}，實際 {style!r}"
        assert "transparent" not in style.lower(), "不可設為透明（會透出底層材質）"
        assert isDarkTheme() in (True, False)


def test_pages_apply_background():
    """四個頁面都必須套用背景色（否則淺色/深色主題下內容區會是系統色）。"""
    import inspect

    from app.ui import account_page, home_page, log_page, settings_page

    for module in (home_page, account_page, log_page, settings_page):
        source = inspect.getsource(module)
        assert "make_background_transparent" in source, f"{module.__name__} 未套用背景"


def test_mica_disabled():
    """不應使用 Mica 半透明材質（會造成主題與內容區底色不一致）。"""
    import inspect

    from app.ui.main_window import MainWindow

    source = inspect.getsource(MainWindow.__init__)
    assert "setMicaEffectEnabled(False)" in source
    assert "setMicaEffectEnabled(True)" not in source


def test_window_has_minimum_size():
    """視窗必須有最小尺寸限制，避免被縮到內容裁切、導覽列收合。"""
    import inspect

    from app.ui.main_window import MainWindow

    assert "setMinimumSize" in inspect.getsource(MainWindow.__init__)


def test_sync_is_safe_without_app():
    """沒有 QApplication 時不應拋出例外。"""
    sync_qt_color_scheme()