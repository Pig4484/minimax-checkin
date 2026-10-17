# v1.0.1

## What's Changed

- Portable build is now isolated by default: ships with `portable.flag`, all data (settings, sessions, logs) stays in `data\` next to the exe and never touches AppData. Delete the flag to share data with the installed version.
- Plaintext session warning: if DPAPI/pywin32 is unavailable, the app now shows a warning after login instead of silently saving plaintext.
- Portable mode forces session encryption (DPAPI) even if the user turned the switch off — a lost USB stick with plaintext cookies would be a direct leak.
- In-app update check: daily automatic check plus a "Check now" button in Settings → About (follows system language: zh-TW / zh-CN / en).

[繁體中文版 ↓](#繁體中文版) | [简体中文版 ↓](#简体中文版)

## Downloads

| Edition | File | Notes |
|---|---|---|
| Installer | `MiniMaxCheckin-Setup-1.0.1-full.exe` (~209MB) | Standard Windows installer: wizard, Start Menu, Apps & features; optional desktop shortcut & autostart; bundled Chromium |
| Portable | `MiniMaxCheckin-Portable-1.0.1-full.zip` (~281MB) | Extract & run; isolated by default (`portable.flag` included); delete the folder to uninstall |

Both builds are console-free GUI (`console=False`), bundled Chromium, trilingual UI (zh-TW / zh-CN / en, follows system language on first run).

## System requirements

- Windows 10 / 11 (x64) with access to `agent.minimax.io`
- Browser engine (any one): bundled Chromium / system Chrome / Edge / in-app download

## Known limitations

- Windows only; first login per account must be completed manually (no captcha handling)
- Credit rules are decided by MiniMax; this tool only records and reports
- Automation is subject to official risk-control policies; use at your own discretion

## Credits

- UI style & stack inspired by [Ghost Downloader 3](https://github.com/XiaoYouChR/Ghost-Downloader-3) (GPL-3.0)
- Fluent widgets: [PySide6-Fluent-Widgets](https://qfluentwidgets.com) (GPL-3.0)
- Dev notes: [docs/dev-notes.md](docs/dev-notes.md)

---

## 繁體中文版

[English ↑](#v101) | [简体中文版 ↓](#简体中文版)

### 更新內容

- 免安裝版預設隔離：內附 `portable.flag`，所有資料（設定、登入狀態、日誌）都寫在 exe 旁的 `data\`，完全不碰 AppData。刪除該旗標即改回與安裝版共用 AppData。
- 明文 session 警告：若 DPAPI／pywin32 不可用，登入後會顯示警告，不再靜默存明文。
- 可攜模式強制加密：即使關掉加密開關，可攜模式仍強制 DPAPI 加密——USB 丟了若是明文 cookie 就是直接外洩。
- 應用內檢查更新：每日自動檢查＋設定 → 關於 →「立即檢查」（跟隨系統語言：繁中／簡中／英文）。

### 下載

| 版本 | 檔案 | 說明 |
|---|---|---|
| 安裝包 | `MiniMaxCheckin-Setup-1.0.1-full.exe`（約 209MB） | 標準 Windows 安裝程式：安裝精靈、開始功能表、控制台新增／移除程式；可選桌面捷徑與開機自啓動；內建 Chromium |
| 免安裝版 | `MiniMaxCheckin-Portable-1.0.1-full.zip`（約 281MB） | 解壓即用；預設隔離（內附 `portable.flag`）；刪除資料夾即移除 |

兩個版本均為無主控台 GUI、內建 Chromium 核心、三語介面（繁中／簡中／英文，首次啟動跟隨系統語言）。

### 系統需求

- Windows 10／11（x64），可連線 `agent.minimax.io`
- 瀏覽器核心三選一：內建 Chromium／系統 Chrome／Edge／程式內下載

### 已知限制

- 需在 Windows 上執行；每個帳號首次登入需手動完成（不處理驗證碼）
- 點數規則由 MiniMax 決定，本工具僅記錄與回報
- 自動化行為受官方風控政策約束，請自行評估使用風險

### 致謝

- 介面風格與技術棧參考 [Ghost Downloader 3](https://github.com/XiaoYouChR/Ghost-Downloader-3)（GPL-3.0）
- Fluent 元件庫 [PySide6-Fluent-Widgets](https://qfluentwidgets.com)（GPL-3.0）

---

## 简体中文版

[English ↑](#v101) | [繁體中文版 ↑](#繁體中文版)

### 更新内容

- 免安装版默认隔离：内置 `portable.flag`，所有数据（设置、登录状态、日志）都写在 exe 旁的 `data\`，完全不碰 AppData。删除该标记即改回与安装版共用 AppData。
- 明文 session 警告：若 DPAPI／pywin32 不可用，登录后会显示警告，不再静默存明文。
- 便携模式强制加密：即使关闭加密开关，便携模式仍强制 DPAPI 加密——U 盘丢了若是明文 cookie 就是直接外泄。
- 应用内检查更新：每日自动检查＋设置 → 关于 →「立即检查」（跟随系统语言：繁中／简中／英文）。

### 下载

| 版本 | 文件 | 说明 |
|---|---|---|
| 安装包 | `MiniMaxCheckin-Setup-1.0.1-full.exe`（约 209MB） | 标准 Windows 安装程序：安装向导、开始菜单、控制面板卸载；可选桌面快捷方式与开机自启；内置 Chromium |
| 免安装版 | `MiniMaxCheckin-Portable-1.0.1-full.zip`（约 281MB） | 解压即用；默认隔离（内置 `portable.flag`）；删除文件夹即移除 |

两个版本均为无控制台 GUI、内置 Chromium 核心、三语界面（繁中／简中／英文，首次启动跟随系统语言）。

### 系统需求

- Windows 10／11（x64），可连接 `agent.minimax.io`
- 浏览器核心三选一：内置 Chromium／系统 Chrome／Edge／程序内下载

### 已知限制

- 需在 Windows 上执行；每个账号首次登录需手动完成（不处理验证码）
- 点数规则由 MiniMax 决定，本工具仅记录与回报
- 自动化行为受官方风控政策约束，请自行评估使用风险

### 致谢

- 界面风格与技术栈参考 [Ghost Downloader 3](https://github.com/XiaoYouChR/Ghost-Downloader-3)（GPL-3.0）
- Fluent 组件库 [PySide6-Fluent-Widgets](https://qfluentwidgets.com)（GPL-3.0）
