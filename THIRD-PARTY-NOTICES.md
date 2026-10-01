# 第三方元件與授權說明

本程式（MiniMax Check-in）以 **GNU General Public License v3.0** 發佈，完整條文見同目錄的
`LICENSE`（或線上版本：<https://www.gnu.org/licenses/gpl-3.0.html>）。
之所以採用 GPL-3.0，是因為使用了以 GPL-3.0 授權的圖形介面元件庫
（PySide6-Fluent-Widgets）。

## 元件清單

| 元件 | 版本（建置時） | 授權 | 用途 |
|---|---|---|---|
| PySide6 / Qt for Python（Qt 6） | 6.11.2 | LGPL-3.0 / GPL-3.0（商業授權另售） | 圖形介面框架 |
| PySide6-Fluent-Widgets | 1.11.3 | **GPL-3.0** | Fluent Design 介面元件 |
| PySideSix-Frameless-Window | 0.8.2 | GPL-3.0 | 無邊框視窗（PySide6-Fluent-Widgets 相依） |
| Playwright（Python） | 1.63.0 | Apache-2.0 | 瀏覽器自動化 |
| Chromium（Playwright 內建版本） | 隨 Playwright 提供 | BSD-3-Clause 等多項開源授權 | 自動化所使用的瀏覽器 |
| loguru | 0.7.x | MIT | 日誌 |
| pywin32 | 312 | PSF-2.0 | Windows DPAPI 加密、具名 Mutex |
| darkdetect | 0.8.0 | BSD-3-Clause | 偵測系統深色模式 |
| Nuitka／PyInstaller（僅建置階段） | PyInstaller 6.22.3 | GPL-2.0 with exception / Apache-2.0 | 打包為執行檔 |
| Inno Setup（僅建置階段） | 6.7.3 | Inno Setup License | 產生安裝程式 |

## GPL-3.0 遵循說明（散布本程式時）

1. 本安裝包已包含 `LICENSE`（GPL-3.0 全文）與本清單，並於安裝精靈中顯示授權頁面。
2. 依 GPL-3.0 第 6 節，散布者必須提供 **對應原始碼（Corresponding Source）** 的取得方式。
   若你修改並重新散布本程式，請同時提供完整原始碼（包含你所做的修改）。
3. 未修改之第三方元件的原始碼可自其官方專案取得（見上表元件名稱對應的官方網站）。
4. Qt 6 係以 LGPL-3.0 授權使用；本程式以動態連結方式使用 Qt 函式庫，未修改 Qt 原始碼。

## 商標聲明

MiniMax、MiniMax Agent 為其各自所有人之商標。本程式為非官方、第三方自動化工具，
與 MiniMax 無任何隸屬或背書關係。