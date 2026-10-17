# v1.0.1

## What's Changed

- Portable build is now isolated by default: ships with `portable.flag`, all data (settings, sessions, logs) stays in `data\` next to the exe and never touches AppData. Delete the flag to share data with the installed version.
- Plaintext session warning: if DPAPI/pywin32 is unavailable, the app now shows a warning after login instead of silently saving plaintext.
- Portable mode forces session encryption (DPAPI) even if the user turned the switch off — a lost USB stick with plaintext cookies would be a direct leak.
- In-app update check: daily automatic check plus a "Check now" button in Settings → About (follows system language: zh-TW / zh-CN / en).

## 下載 / Downloads

| Version | File | Notes |
|---|---|---|
| Installer | `MiniMaxCheckin-Setup-1.0.1-full.exe` (~209MB) | Standard Windows installer: wizard, Start Menu, Apps & features; optional desktop shortcut & autostart; bundled Chromium |
| Portable | `MiniMaxCheckin-Portable-1.0.1-full.zip` (~281MB) | Extract & run; isolated by default (`portable.flag` included); delete the folder to uninstall |

Both builds are console-free GUI (`console=False`), bundled Chromium, trilingual UI (zh-TW / zh-CN / en, follows system language on first run).

## System requirements

- Windows 10 / 11 (x64) with access to `agent.minimax.io`
- Browser engine (any one): bundled Chromium / system Chrome / Edge / in-app download

## 已知限制 / Known limitations

- Windows only; first login per account must be completed manually (no captcha handling)
- Credit rules are decided by MiniMax; this tool only records and reports
- Automation is subject to official risk-control policies; use at your own discretion

## 致謝 / Credits

- UI style & stack inspired by [Ghost Downloader 3](https://github.com/XiaoYouChR/Ghost-Downloader-3) (GPL-3.0)
- Fluent widgets: [PySide6-Fluent-Widgets](https://qfluentwidgets.com) (GPL-3.0)
- Dev notes: [docs/dev-notes.md](docs/dev-notes.md)
