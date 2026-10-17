# Minimax Check-in — MiniMax Agent Daily Auto Check-in

[繁體中文](README_zh-TW.md) | English

Automatically completes the daily check-in at [agent.minimax.io](https://agent.minimax.io)
to claim Credits. Features a **modern Fluent Design GUI** (styled after the open-source
[Ghost Downloader](https://github.com/XiaoYouChR/Ghost-Downloader-3)), **multi-account
management**, and **background scheduling**.

> Same UI stack as Ghost Downloader: **PySide6 + PySide6-Fluent-Widgets**
> (Microsoft Fluent Design) — dark theme, card-style settings, title-bar search,
> system-tray resident.

---

## Features

| Category | Details |
|---|---|
| Check-in | Daily auto check-in, manual run, catch-up on launch, auto retry, randomized delay |
| Multi-account | Isolated session per account; sign in once and reuse; enable / disable / reorder / rename |
| Security | Sessions encrypted with **Windows DPAPI**; plaintext JSON backup optional |
| Verification | Cross-checked against official `signin/status` API — never double-claims |
| Anti-drift | Multi-candidate selectors + text heuristics; warns "app may be outdated" with one-click rescan |
| Resident | Autostart (HKCU Run, no admin), minimize-to-tray, tray menu, notifications, single-instance wake-up |
| Update | Daily update check + "Check now" in Settings → About; trilingual UI (zh-TW / zh-CN / en) |
| Diagnostics | Per-run page HTML, screenshots, API responses; built-in log viewer & export |

---

## Requirements

* Windows 10 / 11 (x64), network access to `agent.minimax.io`
* Browser engine (any one): bundled Chromium (full installer) / system Chrome / Edge / in-app download
* Running from source also needs Python 3.10+ (3.11 recommended)

## Editions

| Edition | File | Notes |
|---|---|---|
| **Installer** | `MiniMaxCheckin-Setup-1.0.1-full.exe` | Wizard, Start Menu, Apps & features; optional shortcut & autostart |
| **Portable** | `MiniMaxCheckin-Portable-1.0.1-full.zip` | Extract & run; isolated by default (`portable.flag`, data in `data\`); delete folder to uninstall |

## Run from source

```bat
setup.bat          :: create .venv, install deps, download Chromium (once)
run.bat            :: launch (pythonw, no console)
run.bat --console  :: launch with console
```

## Data locations

| Location | Contents |
|---|---|
| `%APPDATA%\MinimaxCheckin\` | `config.json` (settings) |
| `%LOCALAPPDATA%\MinimaxCheckin\` | `accounts\` (DPAPI sessions), `logs\`, `diagnostics\` |
| Portable | `data\` next to the exe (isolated) |

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Re-login required" | Session expired → Re-login on the Accounts page |
| Headless fails | Turn off headless mode, or switch to system Chrome |
| "App may be outdated" | Rescan page, update `app/core/selectors.py` per `docs/research/findings.md` |
| Can't quit | X minimizes to tray; right-click tray icon → Quit |

## Tests

```bat
.venv\Scripts\python.exe -m pytest
```

## Limitations

* Windows only; first login per account must be done manually
* Credit rules are decided by MiniMax; this tool only records & reports
* Automation is subject to official risk-control policies

## License & credits

* UI style & stack inspired by [Ghost Downloader 3](https://github.com/XiaoYouChR/Ghost-Downloader-3) (GPL-3.0)
* Fluent widgets: [PySide6-Fluent-Widgets](https://qfluentwidgets.com) (GPL-3.0)
* For personal learning & automation research only

## Development

* Built with **Cline + AI models**, see [docs/dev-notes.md](docs/dev-notes.md).
