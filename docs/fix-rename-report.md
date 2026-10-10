# 修復回報：帳號「重新命名」按鈕無效

- 日期：2026-10-09
- 分支：`main`
- 範圍：僅「重新命名」對話框流程（未動刪除帳號／清除 session／本機資料等其他 MessageBox，未動任何 i18n key）

## 原因（root cause）

**檔案：`app/ui/main_window.py`，舊版 `rename_account`（原 303–327 行）。**

舊程式這樣組對話框：

```python
box = MessageBox(t("notify.account.rename.title"), t("notify.account.rename.body"), self)
edit = LineEdit(box)
edit.setText(account.alias)
...
try:
    box.viewLayout.addWidget(edit)   # ← 這裡一定丟例外
except Exception:
    pass                            # ← 又被靜默吞掉
...
if not box.exec():
    return
ok, reason = self.worker.accounts.rename(account_id, edit.text())
```

問題出在 **qfluentwidgets 1.11.3 的 API 誤用**：

- 專案 import 的 `MessageBox` 定義在 `.venv/.../qfluentwidgets/components/dialog_box/dialog.py:149`，
  類別簽名是 `class MessageBox(MaskDialogBase, Ui_MessageBox)`。
- 它的內部版面（`dialog.py:33–34`、`69–84`）只有 `vBoxLayout` 與 `textLayout`，
  **沒有 `viewLayout` 屬性**。`viewLayout` 只存在於另一個類別 `MessageBoxBase`
  （`message_box_base.py:22`：`self.viewLayout = QVBoxLayout()`）。
- 因此 `box.viewLayout.addWidget(edit)` 丟出 `AttributeError: 'MessageBox' object has no attribute 'viewLayout'`。

**為何使用者看到「直接已重新命名、沒有輸入過程」**（關鍵因果鏈）：

1. `AttributeError` 被 `except Exception: pass` 吞掉 → 輸入框 `edit` **從未加入對話框**。
2. 但 `edit` 早已 `setText(account.alias)`，是個**有預設值（目前別名）但看不到**的輸入框。
3. 使用者按「確定」→ `box.exec()` 回傳 `QDialog.Accepted`（= 1，truthy）→ 沒有 early return。
4. `rename(account_id, edit.text())` 拿到的是**未經修改的舊別名**。
5. `AccountManager.rename` 的校驗裡，「沿用自己現有名稱」不算撞名（`taken`/`others` 都排除了 `account_id` 自己），於是 `rename` 回傳成功。
6. 於是「沒得輸入就直接彈『已重新命名』」，且實際上別名沒變。

補充驗證（離屏實測，非推測）：

- `hasattr(MessageBox(...), "viewLayout")` → `False`；`hasattr(MessageBox(...), "textLayout")` → `True`。
- `MessageBoxBase(...)` 才有 `viewLayout`，`viewLayout.addWidget(edit)` 後 `viewLayout.count()` 正常增加。
- `QDialog.Accepted == 1`、`QDialog.Rejected == 0`，所以 `if not box.exec():` 的判斷邏輯本身是對的，問題從一開始就在「輸入框沒進對話框」。

i18n 不是原因：`notify.account.rename.*`（title/body/ph/ok/cancel/renamed/fail）與
`account.rename.*`（missing/blank/long/taken/same_login）三語 key 皆存在且完整。

## 改了什麼

| 檔案 | 行號範圍 | 說明 |
| --- | --- | --- |
| `app/ui/main_window.py` | 10–25（import 區塊） | 於 `from qfluentwidgets import (...)` 新增 `BodyLabel`、`MessageBoxBase`、`SubtitleLabel` 三個 import（`MessageBox` 保留給 `delete_account` 使用）。 |
| `app/ui/main_window.py` | 306–340（`rename_account` 全文重寫） | 改用 `MessageBoxBase`（有 `viewLayout`）：建立 `SubtitleLabel` 標題 + `BodyLabel` 說明 + 可編輯 `LineEdit`，三者都 `box.viewLayout.addWidget(...)`；輸入框預設值為目前別名、有 placeholder、`setClearButtonEnabled(True)`、`setMinimumWidth(360)`、開對話框即 `setFocus()/selectAll()`；`yesButton/cancelButton` 文案維持走 i18n；`if not box.exec(): return` 保留；成功後 `refresh_all()` 並以 `edit.text().strip()` 當提示內容。移除了會吞例外的 `try/except: pass`。 |
| `tests/test_account.py` | 111–190（新增 6 個測試） | 補 `AccountManager.rename` 核心邏輯迴歸：成功改名+去空白+寫回、擋空白、擋 >24 字（24 字可過）、擋撞別名（沿用自己名字可過）、擋撞別人 `user_name`、找不到帳號。 |
| `tests/test_rename_dialog.py` | 新檔（全文） | UI 對話框迴歸測試，直接驅動真正的 `MainWindow.rename_account`：驗證對話框內有可編輯輸入框且排在 `viewLayout`、預設值為目前別名、有 placeholder；確定改名→真的改名+刷新+成功提示；取消→完全不動；撞名→失敗提示且不刷新；帳號不存在→不彈對話框。用輕量 `_Host(QWidget)` 假視窗＋monkeypatch `MaskDialogBase.exec`（非阻塞）驅動。 |

## 測試

跑了哪些命令與結果：

```
python -m py_compile app/ui/main_window.py tests/test_rename_dialog.py tests/test_account.py
→ OK（無語法錯誤）

.venv\Scripts\python.exe -m pytest tests/ -q
→ 110 passed in 8.27s（全綠，無 failed / error / skipped）
```

額外的「測試有效性」驗證（確認新測試真的抓得到 bug，不是永遠綠）：

- 把 `rename_account` 暫時改回舊的 `MessageBox` 寫法後跑 `pytest tests/test_rename_dialog.py`，
  測試**立刻失敗**並給出精確訊息：
  `AssertionError: 對話框缺少 viewLayout（不可以用 MessageBox）`
  （`assert False where False = hasattr(<...MessageBox...>, 'viewLayout')`）。
  證明測試能攔下此 bug；隨後已還原修復版並再次全綠。
- 舊寫法若沒攔 `exec` 會真的卡住（`MessageBox.exec()` 阻塞等使用者），因此測試統一 patch 共用的
  `MaskDialogBase.exec`，確保任何回退都會「快速失敗」而不是 hang。

手動驗證步驟（給真人操作）：

1. `run.bat --console` 啟動（保留主控台看有無 traceback）。
2. 進「帳號」頁 → 任一帳號卡片點鉛筆「重新命名」。
3. 預期：彈出「重新命名帳號」對話框，**看得到輸入框**、裡面是目前別名（全選狀態）、有 placeholder「例如：主力帳號」。
4. 改成新名字按「確定」→ 右上角 InfoBar「已重新命名」，列表名稱更新。
5. 改成空白／超過 24 字／撞其他帳號別名／撞其他帳號登入名 → 按「確定」應顯示對應失敗原因且不刷新。
6. 按「取消」→ 對話框關閉，名稱不變。
7. 全程主控台不應出現 traceback。

## 風險/後續

- **不影響其他 MessageBox**：`delete_account`（刪除帳號）、`notify.sessions.clear.*`（清除 session）、
  本機資料清除等仍使用 `MessageBox`（純標題+內文+確定/取消，不需自訂輸入框，用法正確），本次完全沒動到。
  `MessageBox` 的 import 也保留（`delete_account` 仍需要）。
- **無 i18n key 變動**：對話框文案全部沿用既有 key（`notify.account.rename.*`），三語不受影響，
  `tests/test_i18n.py::test_locale_files_are_complete` 維持通過。
- **核心校驗完全不變**：`AccountManager.rename`（空白／>24 字／撞別名／撞 `user_name`）一行未改，
  只保留呼叫與結果處理。
- **行為微幅改善（非破壞）**：成功提示內容由舊的 `account.alias`（此時已是新名）改為 `edit.text().strip()`，
  語意等價但更明確；新增開對話框即聚焦並全選文字，純屬體驗提升。
- 後續若還要加「帶輸入框的對話框」，請一律以 `MessageBoxBase` 為基底（見 `docs/qfluentwidgets-messagebox-note.md`），
  不要再對 `MessageBox` 用 `viewLayout`。

## 給主 Agent 的摘要

改了 3 個檔：`app/ui/main_window.py`（`rename_account` 改用 `MessageBoxBase`＋補 3 個 import）、
`tests/test_account.py`（補 6 個 `rename` 核心校驗測試）、新增 `tests/test_rename_dialog.py`（4 個對話框 UI 迴歸測試）。
根因是舊碼對沒有 `viewLayout` 的 `MessageBox` 呼叫 `viewLayout.addWidget` 且用 `try/except: pass` 吞掉 AttributeError，
導致輸入框從未進入對話框。接手請注意：`pytest tests/ -q` 全綠（110 passed），
其他 `MessageBox`（刪除帳號／清除 session）未受影響、i18n 三語未動；另附 `docs/qfluentwidgets-messagebox-note.md` 說明正確用法避免再犯。
