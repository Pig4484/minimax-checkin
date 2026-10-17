# v1.0.1（繁體中文版）

[English →](docs/release-v1.0.1-en.md) | [简体中文版 →](docs/release-v1.0.1.md)

> 下載附件請到 [v1.0.1 Release 頁](https://github.com/Pig4484/minimax-checkin/releases/tag/v1.0.1)（附件只掛在主 release）。

## 更新內容

- 免安裝版預設隔離：內附 `portable.flag`，所有資料（設定、登入狀態、日誌）都寫在 exe 旁的 `data\`，完全不碰 AppData。刪除該旗標即改回與安裝版共用 AppData。
- 明文 session 警告：若 DPAPI／pywin32 不可用，登入後會顯示警告，不再靜默存明文。
- 可攜模式強制加密：即使關掉加密開關，可攜模式仍強制 DPAPI 加密——USB 丟了若是明文 cookie 就是直接外洩。
- 應用內檢查更新：每日自動檢查＋設定 → 關於 →「立即檢查」（跟隨系統語言：繁中／簡中／英文）。

## 下載

| 版本 | 檔案 | 說明 |
|---|---|---|
| 安裝包 | `MiniMaxCheckin-Setup-1.0.1-full.exe`（約 209MB） | 標準 Windows 安裝程式：安裝精靈、開始功能表、控制台新增／移除程式；可選桌面捷徑與開機自啓動；內建 Chromium |
| 免安裝版 | `MiniMaxCheckin-Portable-1.0.1-full.zip`（約 281MB） | 解壓即用；預設隔離（內附 `portable.flag`）；刪除資料夾即移除 |

兩個版本均為無主控台 GUI、內建 Chromium 核心、三語介面（繁中／簡中／英文，首次啟動跟隨系統語言）。

## 系統需求

- Windows 10／11（x64），可連線 `agent.minimax.io`
- 瀏覽器核心三選一：內建 Chromium／系統 Chrome／Edge／程式內下載

## 已知限制

- 需在 Windows 上執行；每個帳號首次登入需手動完成（不處理驗證碼）
- 點數規則由 MiniMax 決定，本工具僅記錄與回報
- 自動化行為受官方風控政策約束，請自行評估使用風險

## 致謝

- 介面風格與技術棧參考 [Ghost Downloader 3](https://github.com/XiaoYouChR/Ghost-Downloader-3)（GPL-3.0）
- Fluent 元件庫 [PySide6-Fluent-Widgets](https://qfluentwidgets.com)（GPL-3.0）
- 開發記錄：[docs/dev-notes.md](docs/dev-notes.md)
