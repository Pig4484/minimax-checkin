"""重新命名對話框的迴歸測試。

背景（本次修的 bug）：
舊版 `MainWindow.rename_account` 用了 `MessageBox`，但 `MessageBox` 只有
`textLayout`、沒有 `viewLayout`；對它呼叫 `box.viewLayout.addWidget(edit)`
會丟 `AttributeError`，而那段被包在 `try/except: pass` 裡，輸入框因此從未
加入對話框。使用者看不到輸入框，按「確定」只會拿 `edit.text()`（仍是預設
的舊別名）去 rename，於是「沒得輸入就說已重新命名」。

本檔直接驅動真正的 `MainWindow.rename_account`，驗證：
1. 對話框內有「可編輯」的輸入框，且確實排在 `viewLayout` 裡、預設值為目前別名；
2. 按確定並改成新名字 → 真的改名 + 刷新 + 成功提示；
3. 按取消 → 完全不動；
4. 撞名 → 顯示失敗提示、不改名、不刷新。
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from app.core.account import AccountManager


def _qt_app():
    return QApplication.instance() or QApplication([])


class _FakeWorker:
    """只提供 rename_account 會用到的 `accounts`。"""

    def __init__(self, accounts: AccountManager) -> None:
        self.accounts = accounts


class _Host(QWidget):
    """rename_account 只需要 self 是 QWidget（當對話框 parent）＋這三個成員。"""

    def __init__(self, accounts: AccountManager) -> None:
        super().__init__()
        self.worker = _FakeWorker(accounts)
        self.info_calls: list[tuple[str, str, bool]] = []
        self.refresh_calls = 0

    def info_bar(self, title: str, content: str, ok: bool = True, duration: int = 5000) -> None:
        self.info_calls.append((title, content, ok))

    def refresh_all(self) -> None:
        self.refresh_calls += 1


def _patch_exec(monkeypatch, on_accept):
    """把對話框的 exec 換成不會阻塞的假實作。

    打在共用的 `MaskDialogBase` 上，`MessageBox` 與 `MessageBoxBase` 都繼承它，
    因此不論實作用哪一種都能攔到，避免回退回舊 bug 時測試卡在真的 exec() 而 hang。
    `on_accept(box)` 可從中斷言對話框內容並模擬使用者輸入；回傳值即 QDialog code。
    """
    from qfluentwidgets.components.dialog_box.mask_dialog_base import MaskDialogBase

    def fake_exec(self):
        return on_accept(self)

    monkeypatch.setattr(MaskDialogBase, "exec", fake_exec)


def _find_edit(box):
    from qfluentwidgets import LineEdit

    edits = box.findChildren(LineEdit)
    assert edits, "對話框內必須有輸入框（LineEdit）"
    return edits[0]


def test_rename_dialog_exposes_editable_input_with_default(monkeypatch, temp_root):
    """對話框必須內含可編輯輸入框，排在 viewLayout、預設值為目前別名。"""
    from app.ui.main_window import MainWindow

    _qt_app()
    manager = AccountManager(encrypt=False)
    account = manager.add("舊別名")

    def on_accept(box):
        # 這是 bug 的核心防線：對話框必須有 viewLayout 且輸入框排在裡面、可編輯。
        assert hasattr(box, "viewLayout"), "對話框缺少 viewLayout（不可以用 MessageBox）"
        edit = _find_edit(box)
        assert box.viewLayout.indexOf(edit) != -1, "輸入框沒有加入 viewLayout"
        assert not edit.isReadOnly(), "輸入框必須可編輯"
        assert edit.text() == "舊別名", f"預設值應為目前別名，實際 {edit.text()!r}"
        assert edit.placeholderText(), "輸入框應有 placeholder"
        # 模擬使用者改成新名字後按「確定」
        edit.setText("新別名")
        return QDialog.Accepted

    _patch_exec(monkeypatch, on_accept)
    host = _Host(manager)
    MainWindow.rename_account(host, account.id)

    assert manager.get(account.id).alias == "新別名"
    assert host.refresh_calls == 1
    assert host.info_calls and host.info_calls[-1][2] is True, "應顯示成功提示"


def test_rename_dialog_cancel_leaves_account_untouched(monkeypatch, temp_root):
    """按取消：不改名、不刷新、不提示。"""
    from app.ui.main_window import MainWindow

    _qt_app()
    manager = AccountManager(encrypt=False)
    account = manager.add("舊別名")

    def on_accept(box):
        edit = _find_edit(box)
        edit.setText("被取消的名字")  # 即便動過，取消後也不該生效
        return QDialog.Rejected

    _patch_exec(monkeypatch, on_accept)
    host = _Host(manager)
    MainWindow.rename_account(host, account.id)

    assert manager.get(account.id).alias == "舊別名"
    assert host.refresh_calls == 0
    assert not host.info_calls


def test_rename_dialog_duplicate_shows_failure(monkeypatch, temp_root):
    """對話框按確定但撞名：顯示失敗提示、不改名、不刷新。"""
    from app.ui.main_window import MainWindow

    _qt_app()
    manager = AccountManager(encrypt=False)
    first = manager.add("甲")
    second = manager.add("乙")

    def on_accept(box):
        edit = _find_edit(box)
        edit.setText("甲")  # 撞 first 的別名
        return QDialog.Accepted

    _patch_exec(monkeypatch, on_accept)
    host = _Host(manager)
    MainWindow.rename_account(host, second.id)

    assert manager.get(second.id).alias == "乙", "撞名不應改動別名"
    assert host.refresh_calls == 0, "失敗不應刷新列表"
    assert host.info_calls and host.info_calls[-1][2] is False, "應顯示失敗提示"


def test_rename_dialog_missing_account_is_noop(monkeypatch, temp_root):
    """帳號不存在：直接返回，不應彈對話框、不應刷新。"""
    from app.ui.main_window import MainWindow

    _qt_app()
    manager = AccountManager(encrypt=False)

    def on_accept(box):  # pragma: no cover - 不該被呼叫
        raise AssertionError("帳號不存在時不應開對話框")

    _patch_exec(monkeypatch, on_accept)
    host = _Host(manager)
    MainWindow.rename_account(host, "does-not-exist")

    assert host.refresh_calls == 0
    assert not host.info_calls
