"""介面主題測試：淺色／深色模式必須正確反映在內容區與卡片。

背景：Qt 6.8+ 的 `QStyleHints.colorScheme()` 預設跟隨 Windows 系統設定；
若 App 選淺色但系統是深色，使用原生調色盤繪製的頁面會變成深色，
出現「標題列是淺色、內容區是深色」的詭異外觀。
"""

from __future__ import annotations

import pytest

from app.ui.components import (
    make_background_transparent,
    refresh_page_backgrounds,
    sync_qt_color_scheme,
)


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
    """歷史遺留的背景 QSS 必須被清除（否則會繼承污染卡片內的文字標籤）。

    實測證實：祖先元件上的無選擇器 ``background: ...`` QSS 會直接套用到
    卡片內的 QLabel，形成「文字背後一塊塊深色方框」。因此該函式必須清除
    殘留背景，且自身不可再設定任何 background。
    """
    from PySide6.QtWidgets import QWidget

    _qt_app()
    for leftover in ("background: #1c1c1c;", "background: #f3f3f3;"):
        widget = QWidget()
        widget.setStyleSheet(leftover)
        make_background_transparent(widget)
        assert "background" not in widget.styleSheet().lower()


def test_refresh_backgrounds_does_not_override_native_theme():
    """不得再對 stackedWidget 強制設定不透明背景（背景屬於 Fluent 原生機制）。

    歷史版本曾在此用 ``#stackedWidget{...}`` 覆寫背景並脫離 QSS 管理，
    實測證實這會關閉亞克力效果並在主題切換時錯色。現在只允許清理殘留。
    """
    from PySide6.QtWidgets import QStackedWidget

    _qt_app()
    stacked = QStackedWidget()
    stacked.setObjectName("stackedWidget")

    class FakeWindow:
        stackedWidget = stacked

    stacked.setStyleSheet("#stackedWidget{background: #ff0000;}")
    refresh_page_backgrounds(FakeWindow())
    assert "background" not in stacked.styleSheet().lower()


def test_pages_apply_background():
    """四個頁面都必須套用背景色（否則淺色/深色主題下內容區會是系統色）。"""
    import inspect

    from app.ui import account_page, home_page, log_page, settings_page

    for module in (home_page, account_page, log_page, settings_page):
        source = inspect.getsource(module)
        assert "make_background_transparent" in source, f"{module.__name__} 未套用背景"


def test_mica_uses_native_mechanism():
    """應使用 Fluent 官方原生背景機制（Mica 開啟），不得強制關閉。

    實測證實：關閉 Mica 又把頁面設為透明，會讓內容區失去底色來源、
    在深淺主題下都錯色。FluentWidget 預設即 Mica 開啟。
    """
    import inspect

    from app.ui.main_window import MainWindow

    source = inspect.getsource(MainWindow.__init__)
    assert "setMicaEffectEnabled(False)" not in source


def test_apply_theme_syncs_window_and_page_backgrounds():
    """_apply_theme 必須同步視窗底色與內容容器調色盤（深淺一致）。

    實測證實三個獨立底色來源：
    1. 視窗 backgroundColor（導覽列／標題列透出它）
    2. 內容容器 QWidget 的 Window 色彩角色（viewport 忽略 QSS）
    3. Qt colorScheme（原生調色盤元件）
    """
    import inspect

    from app.ui.main_window import MainWindow

    source = inspect.getsource(MainWindow._apply_theme)
    assert "sync_page_palettes" in source
    assert "sync_qt_color_scheme" in source
    assert "_normalBackgroundColor" in source


def test_sync_page_palettes_matches_app_theme():
    """內容容器調色盤必須跟隨 App 主題（深色深、淺色淺）。"""
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QWidget
    from PySide6.QtWidgets import QApplication
    from qfluentwidgets import Theme, setTheme

    from app.ui.components import PAGE_PALETTES, sync_page_palettes

    QApplication.instance() or QApplication([])
    page = QWidget()
    container = QWidget(page)
    viewport = QWidget(page)

    class FakePage(QWidget):
        def __init__(self):
            super().__init__()
            self._container = container
            self._viewport = viewport

        def widget(self):
            return self._container

        def viewport(self):
            return self._viewport

    class FakeWindow:
        pass

    fake_page = FakePage()
    for attr in ("homePage", "accountPage", "logPage", "settingsPage"):
        setattr(FakeWindow, attr, fake_page)
    for theme, dark in ((Theme.LIGHT, False), (Theme.DARK, True)):
        setTheme(theme)
        sync_page_palettes(FakeWindow())
        expected = PAGE_PALETTES[dark]["window"].lower()
        for target in (fake_page, container, viewport):
            actual = target.palette().color(QPalette.ColorRole.Window).name().lower()
            assert actual == expected, f"{theme} 下應為 {expected}，實際 {actual}"


def test_window_has_minimum_size():
    """視窗必須有最小尺寸限制，避免被縮到內容裁切、導覽列收合。"""
    import inspect

    from app.ui.main_window import MainWindow

    assert "setMinimumSize" in inspect.getsource(MainWindow.__init__)


def test_sync_is_safe_without_app():
    """沒有 QApplication 時不應拋出例外。"""
    sync_qt_color_scheme()