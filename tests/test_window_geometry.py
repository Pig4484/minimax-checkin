"""?????--minimized?????????????????

????????????????????_preferred_size ????????
? show_window ????????????????????????????????

??????????????? QWidget ? offscreen ????????
??? QWidget ????????
"""
from __future__ import annotations

from app.ui.main_window import MainWindow


class _FakeWin:
    """??? show_window ???????????"""

    def __init__(self, width, height, shown_once=False, pref=None):
        self._w = width
        self._h = height
        self._shown_once = shown_once
        self._pref = pref
        self.activated_layout = False
        self.visible = False

    def _apply_theme(self):
        pass

    def showNormal(self):
        self.visible = True

    def _preferred_size(self):
        if self._pref is not None:
            return self._pref
        return MainWindow._preferred_size()

    def width(self):
        return self._w

    def height(self):
        return self._h

    def resize(self, w, h):
        self._w, self._h = w, h

    class _Layout:
        def __init__(self, owner):
            self._owner = owner

        def activate(self):
            self._owner.activated_layout = True
            return True

    def layout(self):
        return self._Layout(self)

    def update(self):
        pass

    def activateWindow(self):
        pass

    def raise_(self):
        pass


def test_show_window_repairs_hidden_start_geometry():
    """??????????????????????????????"""
    win = _FakeWin(800, 500, shown_once=False, pref=(1100, 720))
    MainWindow.show_window(win)
    assert win.visible
    assert (win.width(), win.height()) == (1100, 720)
    assert win.activated_layout


def test_show_window_keeps_size_when_never_hidden():
    """???????????????????"""
    win = _FakeWin(1000, 700, shown_once=True, pref=(1100, 720))
    MainWindow.show_window(win)
    assert (win.width(), win.height()) == (1000, 700)
    assert not win.activated_layout


def test_show_window_keeps_larger_hidden_window():
    """?????????????????????"""
    win = _FakeWin(1300, 900, shown_once=False, pref=(1100, 720))
    MainWindow.show_window(win)
    assert (win.width(), win.height()) == (1300, 900)
    assert win.activated_layout
