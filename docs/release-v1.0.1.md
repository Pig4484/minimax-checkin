# v1.0.1（简体中文版）

[English →](docs/release-v1.0.1-en.md) | [繁體中文版 →](docs/release-v1.0.1-zh-TW.md)

> 下载附件请到 [v1.0.1 Release 页](https://github.com/Pig4484/minimax-checkin/releases/tag/v1.0.1)（附件只挂在主 release）。

## 更新内容

- 免安装版默认隔离：内置 `portable.flag`，所有数据（设置、登录状态、日志）都写在 exe 旁的 `data\`，完全不碰 AppData。删除该标记即改回与安装版共用 AppData。
- 明文 session 警告：若 DPAPI／pywin32 不可用，登录后会显示警告，不再静默存明文。
- 便携模式强制加密：即使关闭加密开关，便携模式仍强制 DPAPI 加密——U 盘丢了若是明文 cookie 就是直接外泄。
- 应用内检查更新：每日自动检查＋设置 → 关于 →「立即检查」（跟随系统语言：繁中／简中／英文）。

## 下载

| 版本 | 文件 | 说明 |
|---|---|---|
| 安装包 | `MiniMaxCheckin-Setup-1.0.1-full.exe`（约 209MB） | 标准 Windows 安装程序：安装向导、开始菜单、控制面板卸载；可选桌面快捷方式与开机自启；内置 Chromium |
| 免安装版 | `MiniMaxCheckin-Portable-1.0.1-full.zip`（约 281MB） | 解压即用；默认隔离（内置 `portable.flag`）；删除文件夹即移除 |

两个版本均为无控制台 GUI、内置 Chromium 核心、三语界面（繁中／简中／英文，首次启动跟随系统语言）。

## 系统需求

- Windows 10／11（x64），可连接 `agent.minimax.io`
- 浏览器核心三选一：内置 Chromium／系统 Chrome／Edge／程序内下载

## 已知限制

- 需在 Windows 上执行；每个账号首次登录需手动完成（不处理验证码）
- 点数规则由 MiniMax 决定，本工具仅记录与回报
- 自动化行为受官方风控政策约束，请自行评估使用风险

## 致谢

- 界面风格与技术栈参考 [Ghost Downloader 3](https://github.com/XiaoYouChR/Ghost-Downloader-3)（GPL-3.0）
- Fluent 组件库 [PySide6-Fluent-Widgets](https://qfluentwidgets.com)（GPL-3.0）
- 开发记录：[docs/dev-notes.md](docs/dev-notes.md)
