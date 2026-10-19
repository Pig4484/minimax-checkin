# MiniMax Agent 自动签到工具（Minimax Check-in）

[English](README.md) | 简体中文 | [繁體中文](README_zh-TW.md)

自动在 [agent.minimax.io](https://agent.minimax.io) 完成每日签到以领取 Credits，具备
**现代化 Fluent Design 图形界面**（风格参考开源项目
[Ghost Downloader](https://github.com/XiaoYouChR/Ghost-Downloader-3)）、**多账号管理**、
**后台常驻与自动排程**。

> 界面技术与 Ghost Downloader 相同：**PySide6 + PySide6-Fluent-Widgets**（Microsoft Fluent Design），
> 深色主题、卡片式设置页、标题列搜索、系统托盘常驻。

---

## 功能特色

| 分類 | 功能 |
|---|---|
| 签到 | 每日自動签到、立即手動签到、启动时補簽、當日失敗自動重試、随机延遲避免固定时间 |
| 多账号 | 每个账号獨立 session（cookie 完全隔離），登录一次即可長期重複使用；可启用／停用／排序 |
| 安全 | session 以 **Windows DPAPI** 加密儲存（綁定當前 Windows 使用者），亦可选择明文 JSON 方便备份 |
| 判定 | 以官方 `signin/status` API 交叉驗證，**今日已签到时絕不重複點擊**；签到後再做二次驗證 |
| 抗改版 | 多重候選选择器 + 文字啟發式；連續失敗達門檻會提示「**应用可能已过期**」並提供一鍵重新扫描 |
| 常駐 | 开机自启动（HKCU Run，免管理員權限）、关闭窗口縮到系統匣、托盤選單、系統通知 |
| 诊断 | 每次执行的页面 HTML、截圖、API 回應都會存入诊断目錄；內建日志檢視器与匯出 |
| 其他 | 界面主题（深／淺／跟隨系統）、设置搜索、代理伺服器、瀏覽器核心选择、自訂 User-Agent |

---

## 系統需求

* Windows 10／11（x64）
* 网络可連線至 `agent.minimax.io`
* 瀏覽器核心：以下任一即可
  1. 安裝程序的**完整版**已內建 Chromium（免額外下載）
  2. 系統已安裝的 **Google Chrome** 或 **Microsoft Edge**（Windows 內建）
  3. 於程序「设置 → 瀏覽器核心狀態」按「下載核心」（約 150MB）

> 開發／從原始碼执行时另需 Python 3.10 以上（建議 3.11）。

## 兩種發佈版本

| 版本 | 文件 | 說明 |
|---|---|---|
| **安裝包** | `dist\installer\MiniMaxCheckin-Setup-<版本>-full.exe` | 標準 Windows 安裝程序：安裝精靈、開始功能表、**控制台新增/移除程序**、`unins000.exe` 卸載；可選桌面捷徑与开机自启动 |
| **免安裝版** | `dist\portable\MiniMaxCheckin-Portable-<版本>-full.zip` | 解壓即用、不需安裝；功能完全相同；刪除文件夹即移除 |

**兩个版本都不會在桌面產生任何文件**：

* 程序文件一律安裝／解壓到程序目錄（`Program Files`、`%LOCALAPPDATA%\Programs` 或使用者自選位置），
  精靈与 ZIP 內容都**不含**任何 `.lnk`
* 桌面捷徑僅在安裝精靈中由使用者**主動勾選**「建立桌面捷徑（選用）」才會建立（**默认不勾選**）
* 免安裝版 ZIP 內的文件一律包在單一頂層文件夹 `MiniMax Check-in\`，不會散落到解壓位置

## 安裝（安裝包）

到 `dist\installer\` 取得 **`MiniMaxCheckin-Setup-<版本>-full.exe`**，雙擊後依精靈操作：

| 項目 | 說明 |
|---|---|
| 安裝位置 | 默认 `C:\Program Files\MiniMax Check-in`；無管理員權限时自動改为 `%LOCALAPPDATA%\Programs\MiniMax Check-in` |
| 開始功能表 | 建立「MiniMax 自動签到」与「卸載 MiniMax 自動签到」捷徑（一律建立） |
| 桌面捷徑 | 選項，**默认不勾選** |
| 开机自启动 | 選項，**默认不勾選**（也可在程序设置中隨时開關） |
| 新增／移除程序 | 註冊於「应用程序与功能」，显示版本与大小 |
| **卸載** | 控制台卸載、開始功能表「卸載」，或 `{安裝目錄}\unins000.exe`；卸載时詢問是否一併刪除设置与账号資料（**默认保留**） |
| 安裝範圍 | 默认「僅为我安裝」（免管理員權限），也可在精靈中改为所有人 |

靜默安裝（批次部署）：

```bat
MiniMaxCheckin-Setup-1.0.0-full.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
MiniMaxCheckin-Setup-1.0.0-full.exe /VERYSILENT /DIR="D:\Apps\MiniMax Check-in"
```

## 使用（免安裝版）

1. 解壓縮 `MiniMaxCheckin-Portable-1.0.0-full.zip` 到**程序專用文件夹**（例如 `D:\Apps\`）
   — 請勿解壓到桌面（ZIP 內附 `免安裝版說明.txt` 也有提醒）
2. 雙擊 `MiniMax Check-in\MinimaxCheckin.exe` 启动
3. 移除方式：直接刪除文件夹；若曾打开「開機自啓启动」，請先在程序设置中关闭

> 免安裝版**默认仍將資料存在 AppData**（与安裝版相同，符合 Windows 慣例）。
> 若要做成可放 USB 的完全可攜版本，請在程序文件夹內新增空文件 `portable.flag`，
> 之後所有資料會改存到該文件夹的 `data\` 子文件夹。

## 從原始碼执行

```bat
setup.bat          :: 一鍵建立 .venv、安裝依賴、下載 Chromium（只需执行一次）
```

| 启动方式 | 操作 |
|---|---|
| **桌面捷徑** | 雙擊桌面上的 **`MiniMax 自動签到`** 圖示 |
| 批次檔 | 雙擊專案目錄下的 **`run.bat`** |
| 看得到訊息 | 雙擊 **`run.bat --console`**（或命令列执行 `.venv\Scripts\python.exe main.py`） |

> ⚠️ 不要直接雙擊 `main.py`：那會用系統的 Python 执行，缺少套件而報錯。
> 程序启动後若沒看到窗口，請檢查**系統匣**（右下角 ^ 圖示區）。

## 資料存放位置（遵循 Windows 慣例）

| 位置 | 內容 | 为什麼 |
|---|---|---|
| `%APPDATA%\MinimaxCheckin\` | `config.json`（所有设置） | **Roaming**：屬於使用者偏好，會隨使用者设置檔在網域環境中漫遊 |
| `%LOCALAPPDATA%\MinimaxCheckin\` | `accounts\`（登录 session）、`logs\`、`diagnostics\`、`state.json`、`browsers\` | **Local**：登录 session 以 Windows DPAPI 加密，金鑰綁定「本機＋目前使用者」，複製到別台電腦也無法解密；日志与诊断檔也屬機器相關資料，放 Roaming 只會產生無用的同步流量 |

* 舊版（全放在 Roaming）首次启动會**自動搬移**执行期資料到 Local，设置檔留在 Roaming
* 程序「设置 → 文件位置」可直接打开上述目錄，並可一鍵清除日志／诊断檔
* **可攜模式**：在程序旁放置 `portable.flag`（或设置環境變數 `MINIMAXCHECKIN_PORTABLE=1`），
  所有資料改存於程序目錄下的 `data\`，完全不寫入 AppData
* 解除安裝时可选择是否一併刪除上述資料（默认保留）

## 建置与發佈（打包成安裝程序）

```bat
build.bat                 :: 完整版：內建 Chromium → 安裝包 + 免安裝版（ZIP 約 200MB）
build.bat lite            :: 精簡版：不內建瀏覽器核心（ZIP 約 55MB）
build.bat --no-installer  :: 只產生执行檔与免安裝版，不產生安裝包
build.bat --no-portable   :: 只產生安裝包
```

首次执行會自動準備 **PyInstaller** 与 **Inno Setup 6 可攜版**（下載到 `%LOCALAPPDATA%\MinimaxCheckin-build`，
不寫入系統登錄檔、不影響已安裝的其他软件）。

輸出：

```
dist\MinimaxCheckin\                                      可直接执行的程序目錄
dist\installer\MiniMaxCheckin-Setup-<版本>-<flavor>.exe    安裝包（含卸載）
dist\portable\MiniMaxCheckin-Portable-<版本>-<flavor>.zip  免安裝版（解壓即用）
```

手動流程（等同 build.bat 做的事）：

```bat
.venv\Scripts\python.exe -m PyInstaller --noconfirm build_tools\MinimaxCheckin.spec --distpath dist --workpath build
build_tools\bootstrap_inno.py                     :: 取得 Inno Setup（可攜）
%LOCALAPPDATA%\MinimaxCheckin-build\inno\ISCC.exe /DAppVersion=1.0.0 /DFlavor=full build_tools\installer.iss
```

打包細節：PyInstaller `onedir` 模式（启动較快）；已排除大量未使用的 Qt 模組
（QtWebEngine、QtQuick、Qt3D、Multimedia 等）以縮小體積；版本資源与
`app/constants.py` 的 `APP_VERSION` 自動同步。


## 使用流程

1. 启动程序 → 切到「**账号**」页 → 按「**新增账号**」
2. 程序會打开瀏覽器窗口並**直接进入 MiniMax 登录页**（`Welcome to MiniMax`），
   並在程序畫面显示轉圈圈进度（启动瀏覽器 → 連線 → 打开登录页 → 就緒）
3. 在該窗口选择登录方式（Email 验证码／Continue with Google／Continue With Github）
4. 登录成功後程序會自動偵測並儲存 session，並关闭該窗口（**之後不必再登录**）
5. 回到「总览」页按「**立即签到**」即可測試；成功後會显示獲得的點數
6. 到「设置」页设置每日自動签到时间，並視需要打开「开机自启动」

**登录过程的错误提示**（不會讓你白等）：

| 狀況 | 提示 |
|---|---|
| 沒有网络／DNS 失敗 | 「無法連線」＋請檢查网络連線（**启动瀏覽器前就先檢查**） |
| 代理伺服器问题 | 「代理伺服器问题」＋請檢查设置中的代理伺服器 |
| TLS／凭证错误 | 「凭证错误」＋可能是网络環境或代理攔截 |
| 連線超时 | 「登录超时」＋网络过慢或被阻擋 |
| 你關掉了瀏覽器窗口 | 「窗口已关闭」＋**立即**回報，不需等超时 |
| 不想繼續 | 可隨时关闭窗口或取消，程序會立即停止等待（等待上限 5 分鐘） |
| 剛好在自動签到 | 會先显示「正在等待目前的签到作業結束…」，待签到完成才打开登录窗口（避免兩者互相重啟瀏覽器） |
| 螢幕較小或縮放較大 | 登录窗口會自動最大化；若內容仍高於窗口，登录页會**自動等比縮放**，確保最下方的登录選項都在畫面內 |
| 界面主题顏色不對 | 已修正：App 主题會強制覆寫 Qt 的 `colorScheme`，因此「淺色」不受 Windows 深色模式影響；设置切換後立即生效 |

## 常見問答

**Q：执行时會出现 CMD 黑窗嗎？**
不會。主程序与安裝程序都是 GUI 子系統（PE subsystem=2，已实測驗證）。
若你想看执行訊息，可执行 `run.bat --console`（僅開發模式）。

**Q：可以在沒有安裝 Chrome／Edge 的電腦上用嗎？**
可以。完整版安裝包已內建 Chromium，不需任何額外瀏覽器。
精簡版則會自動改用系統的 Chrome／Edge，或可在设置页一鍵下載核心。

> 登录一律由使用者手動完成（本工具**不做验证码或風控繞过**）。

---

## 设置項目

**一般**：界面主题、开机自启动、启动时縮到系統匣、关闭窗口时縮到系統匣、只允許一个实例

**签到**：每日执行时间（可選时／分）、随机延遲（±0~180 分）、启动时補簽、页面超时、
失敗重試次數／间隔、無頭模式、無頭失敗改用显示窗口重試、执行後保留瀏覽器窗口

**账号**：同时处理账号數（1~3，建議 1）、加密儲存 session、打开資料目錄、清除所有登录狀態

**通知**：签到成功／失敗／需要重新登录时的系統通知

**进階**：瀏覽器核心（內建 Chromium／系統 Chrome／Edge）、代理伺服器、自訂 User-Agent、
日志等級与保留天數、改版偵測門檻、日志／诊断／專案文件夹

資料与设置位置：`%APPDATA%\MinimaxCheckin\`
（`config.json`、`accounts\`、`logs\`、`diagnostics\`、`state.json`）

---

## 运作原理（逆向研究摘要）

完整研究報告見 **[docs/research/findings.md](docs/research/findings.md)**。

1. **登录**：`account.minimax.io/unified-login` 走 OAuth2 授權碼流程，回呼到
   `agent.minimax.io/auth/callback`。登录後 token（JWT，約 40 天有效）存放於
   `localStorage._token`（同时存在 cookie `_token`），因此只要保存 Playwright
   `storage_state` 就能还原登录，**不需密碼**。
2. **签到 API**：
   * `GET /minimax-cloud/api/v1/signin/status` → `days[].status`：`1` 未解鎖、`2` 今日可簽、`3` 已领取
   * `POST /minimax-cloud/api/v1/signin/claim`（body `{}`）→ `claim_result: 1`、`points`、`day_no`
3. **为何用瀏覽器而非純 HTTP**：官方 API 要求 `x-signature` / `yy` 等 MD5 簽章標頭，
   实測直接呼叫會回 `HTTP 400 {"error":"invalid signature"}`。因此本工具以
   **Playwright 操作真实 UI**（由官方前端自行帶上正確簽章），再用
   **攔截官方 API 回應**取得結構化結果 —— 免逆向簽章、又能精準判斷成敗。
4. **判斷流程**：載入页面 → 攔截 `signin/status` → `status == 3` 直接判定今日已签到（不點擊）；
   `status == 2` → 等待 `[data-testid="signin-card"]` 出现 → 點擊 `button.signin-claim-button`
   → 解析 `signin/claim` 回應 → 面板消失作为二次驗證。
5. **抗改版**：选择器有版本（見 `app/constants.py` 的 `SELECTOR_PACK_VERSION`）並依序嘗試
   多个候選与文字特徵；連續失敗達門檻时提示应用可能过期，並可用 `tools/probe.py`
   重新扫描页面產生新的选择器資訊与诊断檔。

---

## 疑難排解

| 症狀 | 处理方式 |
|---|---|
| 显示「需要重新登录」 | session 过期（token 約 40 天）→ 到「账号」页按「重新登录」 |
| 無頭模式簽不成功 | 关闭设置中的「無頭模式」（改用显示窗口），或改「瀏覽器核心」为系統 Chrome；程序也會自動嘗試显示窗口重試 |
| 提示「应用可能已过期」 | MiniMax 可能已改版 → 按「重新扫描页面」，並参考 `docs/research/findings.md` 更新 `app/core/selectors.py` 後遞增 `SELECTOR_PACK_VERSION` |
| 想看签到过程 | 设置 →「执行後保留瀏覽器窗口」＋关闭「無頭模式」 |
| 出现「點擊未成功」 | 通常是官方公告彈窗蓋住页面（程序會自動关闭並重試）；若仍失敗，檢查诊断目錄的 `after_claim.png` |
| 程序關不掉 | 窗口 X 只會縮到系統匣；請用托盤圖示右鍵 →「結束」 |
| 想確認流程是否仍有效 | 执行 `.venv\Scripts\python.exe tools\verify_session.py --headed` |

## 改版維護流程

```bat
:: 1) 扫描目前页面（輸出候選元素、指紋与截圖到 diagnostics 目錄）
.venv\Scripts\python.exe tools\probe.py --headed

:: 1b) 對真实站台跑一次完整签到流程（今日已签到时只會回報「已签到」）
.venv\Scripts\python.exe tools\verify_session.py --headed

:: 2) 對照 docs/research/findings.md 的选择器表，更新 app/core/selectors.py
::    （候選选择器定義在 app/constants.py）

:: 3) 更新 tests/fixtures/*.html 並执行測試
.venv\Scripts\python.exe -m pytest

:: 4) 遞增 app/constants.py 的 SELECTOR_PACK_VERSION
```

## 專案結構

```
Minimax Check-in/
├─ main.py                     # 进入點（單一实例、--minimized）
├─ setup.bat / run.bat         # 安裝与启动
├─ app/
│  ├─ config.py  paths.py  constants.py  logger.py
│  ├─ worker.py                # 背景执行緒（asyncio + Playwright）+ Qt 訊号
│  ├─ core/
│  │  ├─ browser.py            # 單一瀏覽器 + 每账号隔離 context、互動登录擷取
│  │  ├─ checkin.py            # 签到流程狀態機（攔截 API 回應做驗證）
│  │  ├─ selectors.py          # 选择器引擎（多候選 + 文字啟發式 + 指紋）
│  │  ├─ engine.py             # 多账号执行、結果彙總、改版計數
│  │  ├─ scheduler.py          # 每日排程 + 随机延遲 + 補簽 + 重試
│  │  ├─ account.py  crypto.py # 账号与 DPAPI 加密 session
│  │  ├─ state.py  autostart.py  diagnostics.py
│  └─ ui/
│     ├─ main_window.py        # FluentWindow + 左側導覽 + 标题列搜索 + 系統匣
│     ├─ home_page.py / account_page.py / log_page.py / settings_page.py
│     ├─ components.py         # 自訂 Fluent 设置卡片与狀態元件
│     └─ icon.py               # 程序繪製的 App 圖示
├─ tools/probe.py              # 页面重新扫描（改版时使用）
├─ tools/verify_session.py     # 對真实站台驗證签到流程
├─ tests/                      # pytest（113 項，含实測 fixture）
└─ docs/research/findings.md   # 逆向研究報告（API／DOM／狀態語意）
```

## 測試

```bat
.venv\Scripts\python.exe -m pytest
```

涵蓋：选择器引擎（以实測 HTML fixture 離線驗證）、API 回應解析、设置正規化与持久化、
DPAPI 加解密往返、账号管理、签到結果狀態機、排程时间与随机延遲計算。

## 已知限制

* 需在 Windows 上执行（DPAPI 加密、开机自启动、系統匣通知皆为 Windows 功能）
* 登录需使用者手動完成一次（不处理验证码）
* 點數規則（800／2,000 等）由 MiniMax 決定，本工具僅记录与回報，不保證收益
* 若官方改为需要互動式人機驗證，無頭模式可能失效，請改用显示窗口或系統 Chrome
* 自動化行为仍受官方風控政策約束，請自行評估使用風險並適度使用

## 授權与致謝

* 界面风格与技術棧参考 [Ghost Downloader 3](https://github.com/XiaoYouChR/Ghost-Downloader-3)（GPL-3.0）
* Fluent Design 元件庫：[PySide6-Fluent-Widgets](https://qfluentwidgets.com)（GPL-3.0）
* 本專案僅供个人學習与自動化研究使用

## 開發方式

* 本專案以 **Cline + AI 模型協作**開發，詳見 [docs/dev-notes.md](docs/dev-notes.md)。

