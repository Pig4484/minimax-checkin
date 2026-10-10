# qfluentwidgets 1.11.3 對話框正確用法筆記

> 緣起：本次「重新命名」bug 就是誤用 `MessageBox` 造成。此筆記供日後加「帶輸入框的對話框」時參考。
> 套件路徑：`.venv/Lib/site-packages/qfluentwidgets/components/dialog_box/`

## 兩個容易搞混的類別

| 類別 | 定義位置 | 有沒有 `viewLayout` | 用途 |
| --- | --- | --- | --- |
| `MessageBox` | `dialog.py:149`（`class MessageBox(MaskDialogBase, Ui_MessageBox)`） | **沒有**（只有 `vBoxLayout` + `textLayout`，見 `dialog.py:33-34,69-84`） | 純「標題＋內文＋確定/取消」，**不要**往裡塞自訂 widget |
| `MessageBoxBase` | `message_box_base.py:12` | **有**（`self.viewLayout = QVBoxLayout()`，見 `:22`） | 需要**自訂內容／輸入框**時的正確基底 |

兩者都繼承 `MaskDialogBase`（`mask_dialog_base.py:10`），`exec()` 都是繼承自 `QDialog`（都沒有自己 override）。

## 正確做法（帶輸入框）

```python
from qfluentwidgets import BodyLabel, LineEdit, MessageBoxBase, SubtitleLabel

box = MessageBoxBase(self)                       # parent 傳主視窗
box.viewLayout.addWidget(SubtitleLabel("標題"))   # 自訂標題
box.viewLayout.addWidget(BodyLabel("說明文字"))    # 自訂說明（可 setWordWrap(True)）
edit = LineEdit()                                 # 輸入框不需要傳 box 當 parent
edit.setText(目前值)
edit.setPlaceholderText("提示")
box.viewLayout.addWidget(edit)
box.yesButton.setText("確定")
box.cancelButton.setText("取消")
box.widget.setMinimumWidth(360)                   # 太窄時給個最小寬度
edit.setFocus(); edit.selectAll()                 # 開對話框即聚焦全選（體驗）

if not box.exec():        # 按取消/關閉 → QDialog.Rejected(0) → early return
    return
value = edit.text()       # 按「確定」後才讀
```

## exec() 回傳值語意

- `QDialog.Accepted == 1`（truthy）：按「確定」（`yesButton`）。
- `QDialog.Rejected == 0`（falsy）：按「取消」或關閉（`cancelButton`）。
- 所以 `if not box.exec(): return` 是正確判斷，問題永遠不在這行，而在「輸入框有沒有真的進對話框」。

## 地雷清單（避免再犯）

1. **不要**對 `MessageBox` 用 `box.viewLayout`——會 `AttributeError`。
2. **不要**用 `try/except: pass` 包住 `viewLayout.addWidget`——錯誤會被吞，輸入框無聲消失，
   使用者會以為「沒得輸入就成功了」。
3. `LineEdit` 不必（也不該）傳 `box` 當 parent；交給 `viewLayout.addWidget` 管理父子關係即可。
4. 純確認框（不需輸入）繼續用 `MessageBox` 是對的，不必改。
5. 寫測試時若 patch `exec` 避免阻塞，patch 共用的 `MaskDialogBase.exec` 最穩（同時涵蓋兩種類別），
   並在 callback 裡斷言 `hasattr(box, "viewLayout")` 與「輸入框在 viewLayout 內」，即可精準防回退。
