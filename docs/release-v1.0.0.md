# v1.0.0 Release notes（草稿）

## MiniMax Check-in v1.0.0 — 首次公開發行

自動在 [agent.minimax.io](https://agent.minimax.io) 完成每日簽到以領取 Credits，
具備現代化 Fluent Design GUI（風格參考開源專案
[Ghost Downloader](https://github.com/XiaoYouChR/Ghost-Downloader-3)）、多帳號管理、背景常駐與自動排程。

### 下載

| 版本 | 檔案 | 說明 |
|---|---|---|
| 安裝包 | `MiniMaxCheckin-Setup-1.0.0-full.exe`（約 209MB） | 標準 Windows 安裝程式：安裝精靈、開始功能表、控制台新增/移除程式；可選桌面捷徑與開機自啓動；內建 Chromium，免額外下載 |
| 免安裝版 | `MiniMaxCheckin-Portable-1.0.0-full.zip`（約 281MB） | 解壓即用；功能完全相同；刪除資料夾即移除 |

兩個版本均為無主控台 GUI（`console=False`）、內建 Chromium 核心、三語介面（繁中／簡中／英文，首次啟動跟隨系統語言）。

### 功能

- 每日自動簽到、立即手動簽到、啟動時補簽、當日失敗自動重試、隨機延遲
- 多帳號：每帳號獨立 session（cookie 完全隔離），登入一次長期重用；可啟用／停用／排序／重新命名
- 安全：session 以 Windows DPAPI 加密儲存，亦可選明文 JSON 備份
- 判定：以官方 `signin/status` API 交叉驗證，今日已簽到絕不重複點擊；簽到後二次驗證
- 抗改版：多重候選選擇器＋文字啟發式；連續失敗達門檻提示「應用可能已過期」並可一鍵重新掃描
- 常駐：開機自啓動（HKCU Run，免管理員權限）、關閉視窗縮到系統匣、托盤選單、系統通知、單一實例喚醒
- 診斷：每次執行的頁面 HTML、截圖、API 回應存入診斷目錄；內建日誌檢視器與匯出

### 系統需求

- Windows 10／11（x64），可連線 `agent.minimax.io`
- 瀏覽器核心三選一：安裝包內建 Chromium／系統 Chrome／Edge／程式內下載

### 已知限制

- 需在 Windows 上執行；登入需使用者手動完成一次（不處理驗證碼）
- 點數規則由 MiniMax 決定，本工具僅記錄與回報
- 自動化行為受官方風控政策約束，請自行評估使用風險

### 致謝

- 介面風格與技術棧參考 [Ghost Downloader 3](https://github.com/XiaoYouChR/Ghost-Downloader-3)（GPL-3.0）
- Fluent 元件庫 [PySide6-Fluent-Widgets](https://qfluentwidgets.com)（GPL-3.0）
- 詳見 [docs/dev-notes.md](docs/dev-notes.md)
