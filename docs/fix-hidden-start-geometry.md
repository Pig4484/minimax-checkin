# 隱藏啟動窄窗修復（--minimized 從托盤還原偏窄）

- 症狀：開機自啓動後從托盤點出主視窗，寬度偏窄、搜尋框溢出標題列、統計卡被裁、底部被切、導覽列收合；碰一下標題列就自己恢復正常。桌面捷徑啟動則正常。
- 根因：開機時螢幕可用範圍尚未穩定，`MainWindow._preferred_size()` 算出過小尺寸並永久沿用；`main.py --minimized` 直接 `hide()` 從未 show，佈局沒走首次顯示計算；`show_window()` 只有 showNormal，沒有尺寸／佈局兜底。
- 修法：`MainWindow._shown_once` ＋ `showEvent` 標記；`show_window()` 在隱藏啟動後首次顯示時 grow-only 到偏好尺寸並 `layout().activate()`。已顯示過的不動（尊重使用者手動調整的尺寸）。
- 測試：`tests/test_window_geometry.py`（3 個：修復過小／不動已顯示／夠大只激活不縮小）。
