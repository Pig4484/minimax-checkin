# MiniMax Agent 自動簽到工具（Minimax Check-in）

自動在 [agent.minimax.io](https://agent.minimax.io) 完成每日簽到以領取 Credits，具備
**現代化 Fluent Design 圖形介面**（風格參考開源專案
[Ghost Downloader](https://github.com/XiaoYouChR/Ghost-Downloader-3)）、**多帳號管理**、
**背景常駐與自動排程**。

> 介面技術與 Ghost Downloader 相同：**PySide6 + PySide6-Fluent-Widgets**（Microsoft Fluent Design），
> 深色主題、卡片式設定頁、標題列搜尋、系統匣常駐。

---

## 功能特色

| 分類 | 功能 |
|---|---|
| 簽到 | 每日自動簽到、立即手動簽到、啟動時補簽、當日失敗自動重試、隨機延遲避免固定時間 |
| 多帳號 | 每個帳號獨立 session（cookie 完全隔離），登入一次即可長期重複使用；可啟用／停用／排序 |
| 安全 | session 以 **Windows DPAPI** 加密儲存（綁定當前 Windows 使用者），亦可選擇明文 JSON 方便備份 |
| 判定 | 以官方 `signin/status` API 交叉驗證，**今日已簽到時絕不重複點擊**；簽到後再做二次驗證 |
| 抗改版 | 多重候選選擇器 + 文字啟發式；連續失敗達門檻會提示「**應用可能已過期**」並提供一鍵重新掃描 |
| 常駐 | 開機自啓動（HKCU Run，免管理員權限）、關閉視窗縮到系統匣、托盤選單、系統通知 |
| 診斷 | 每次執行的頁面 HTML、截圖、API 回應都會存入診斷目錄；內建日誌檢視器與匯出 |
| 其他 | 介面主題（深／淺／跟隨系統）、設定搜尋、代理伺服器、瀏覽器核心選擇、自訂 User-Agent |

---

## 系統需求

* Windows 10／11（x64）
* 網路可連線至 `agent.minimax.io`
* 瀏覽器核心：以下任一即可
  1. 安裝程式的**完整版**已內建 Chromium（免額外下載）
  2. 系統已安裝的 **Google Chrome** 或 **Microsoft Edge**（Windows 內建）
  3. 於程式「設定 → 瀏覽器核心狀態」按「下載核心」（約 150MB）

> 開發／從原始碼執行時另需 Python 3.10 以上（建議 3.11）。

## 兩種發佈版本

| 版本 | 檔案 | 說明 |
|---|---|---|
| **安裝包** | `dist\installer\MiniMaxCheckin-Setup-<版本>-full.exe` | 標準 Windows 安裝程式：安裝精靈、開始功能表、**控制台新增/移除程式**、`unins000.exe` 卸載；可選桌面捷徑與開機自啓動 |
| **免安裝版** | `dist\portable\MiniMaxCheckin-Portable-<版本>-full.zip` | 解壓即用、不需安裝；功能完全相同；刪除資料夾即移除 |

**兩個版本都不會在桌面產生任何檔案**：

* 程式檔案一律安裝／解壓到程式目錄（`Program Files`、`%LOCALAPPDATA%\Programs` 或使用者自選位置），
  精靈與 ZIP 內容都**不含**任何 `.lnk`
* 桌面捷徑僅在安裝精靈中由使用者**主動勾選**「建立桌面捷徑（選用）」才會建立（**預設不勾選**）
* 免安裝版 ZIP 內的檔案一律包在單一頂層資料夾 `MiniMax Check-in\`，不會散落到解壓位置

## 安裝（安裝包）

到 `dist\installer\` 取得 **`MiniMaxCheckin-Setup-<版本>-full.exe`**，雙擊後依精靈操作：

| 項目 | 說明 |
|---|---|
| 安裝位置 | 預設 `C:\Program Files\MiniMax Check-in`；無管理員權限時自動改為 `%LOCALAPPDATA%\Programs\MiniMax Check-in` |
| 開始功能表 | 建立「MiniMax 自動簽到」與「卸載 MiniMax 自動簽到」捷徑（一律建立） |
| 桌面捷徑 | 選項，**預設不勾選** |
| 開機自啓動 | 選項，**預設不勾選**（也可在程式設定中隨時開關） |
| 新增／移除程式 | 註冊於「應用程式與功能」，顯示版本與大小 |
| **卸載** | 控制台卸載、開始功能表「卸載」，或 `{安裝目錄}\unins000.exe`；卸載時詢問是否一併刪除設定與帳號資料（**預設保留**） |
| 安裝範圍 | 預設「僅為我安裝」（免管理員權限），也可在精靈中改為所有人 |

靜默安裝（批次部署）：

```bat
MiniMaxCheckin-Setup-1.0.0-full.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
MiniMaxCheckin-Setup-1.0.0-full.exe /VERYSILENT /DIR="D:\Apps\MiniMax Check-in"
```

## 使用（免安裝版）

1. 解壓縮 `MiniMaxCheckin-Portable-1.0.0-full.zip` 到**程式專用資料夾**（例如 `D:\Apps\`）
   — 請勿解壓到桌面（ZIP 內附 `免安裝版說明.txt` 也有提醒）
2. 雙擊 `MiniMax Check-in\MinimaxCheckin.exe` 啟動
3. 移除方式：直接刪除資料夾；若曾開啟「開機自啓啟動」，請先在程式設定中關閉

> 免安裝版**預設仍將資料存在 AppData**（與安裝版相同，符合 Windows 慣例）。
> 若要做成可放 USB 的完全可攜版本，請在程式資料夾內新增空檔案 `portable.flag`，
> 之後所有資料會改存到該資料夾的 `data\` 子資料夾。

## 從原始碼執行

```bat
setup.bat          :: 一鍵建立 .venv、安裝依賴、下載 Chromium（只需執行一次）
```

| 啟動方式 | 操作 |
|---|---|
| **桌面捷徑** | 雙擊桌面上的 **`MiniMax 自動簽到`** 圖示 |
| 批次檔 | 雙擊專案目錄下的 **`run.bat`** |
| 看得到訊息 | 雙擊 **`run.bat --console`**（或命令列執行 `.venv\Scripts\python.exe main.py`） |

> ⚠️ 不要直接雙擊 `main.py`：那會用系統的 Python 執行，缺少套件而報錯。
> 程式啟動後若沒看到視窗，請檢查**系統匣**（右下角 ^ 圖示區）。

## 資料存放位置（遵循 Windows 慣例）

| 位置 | 內容 | 為什麼 |
|---|---|---|
| `%APPDATA%\MinimaxCheckin\` | `config.json`（所有設定） | **Roaming**：屬於使用者偏好，會隨使用者設定檔在網域環境中漫遊 |
| `%LOCALAPPDATA%\MinimaxCheckin\` | `accounts\`（登入 session）、`logs\`、`diagnostics\`、`state.json`、`browsers\` | **Local**：登入 session 以 Windows DPAPI 加密，金鑰綁定「本機＋目前使用者」，複製到別台電腦也無法解密；日誌與診斷檔也屬機器相關資料，放 Roaming 只會產生無用的同步流量 |

* 舊版（全放在 Roaming）首次啟動會**自動搬移**執行期資料到 Local，設定檔留在 Roaming
* 程式「設定 → 檔案位置」可直接開啟上述目錄，並可一鍵清除日誌／診斷檔
* **可攜模式**：在程式旁放置 `portable.flag`（或設定環境變數 `MINIMAXCHECKIN_PORTABLE=1`），
  所有資料改存於程式目錄下的 `data\`，完全不寫入 AppData
* 解除安裝時可選擇是否一併刪除上述資料（預設保留）

## 建置與發佈（打包成安裝程式）

```bat
build.bat                 :: 完整版：內建 Chromium → 安裝包 + 免安裝版（ZIP 約 200MB）
build.bat lite            :: 精簡版：不內建瀏覽器核心（ZIP 約 55MB）
build.bat --no-installer  :: 只產生執行檔與免安裝版，不產生安裝包
build.bat --no-portable   :: 只產生安裝包
```

首次執行會自動準備 **PyInstaller** 與 **Inno Setup 6 可攜版**（下載到 `%LOCALAPPDATA%\MinimaxCheckin-build`，
不寫入系統登錄檔、不影響已安裝的其他軟體）。

輸出：

```
dist\MinimaxCheckin\                                      可直接執行的程式目錄
dist\installer\MiniMaxCheckin-Setup-<版本>-<flavor>.exe    安裝包（含卸載）
dist\portable\MiniMaxCheckin-Portable-<版本>-<flavor>.zip  免安裝版（解壓即用）
```

手動流程（等同 build.bat 做的事）：

```bat
.venv\Scripts\python.exe -m PyInstaller --noconfirm build_tools\MinimaxCheckin.spec --distpath dist --workpath build
build_tools\bootstrap_inno.py                     :: 取得 Inno Setup（可攜）
%LOCALAPPDATA%\MinimaxCheckin-build\inno\ISCC.exe /DAppVersion=1.0.0 /DFlavor=full build_tools\installer.iss
```

打包細節：PyInstaller `onedir` 模式（啟動較快）；已排除大量未使用的 Qt 模組
（QtWebEngine、QtQuick、Qt3D、Multimedia 等）以縮小體積；版本資源與
`app/constants.py` 的 `APP_VERSION` 自動同步。


## 使用流程

1. 啟動程式 → 切到「**帳號**」頁 → 按「**新增帳號**」
2. 程式會開啟瀏覽器視窗並**直接進入 MiniMax 登入頁**（`Welcome to MiniMax`），
   並在程式畫面顯示轉圈圈進度（啟動瀏覽器 → 連線 → 開啟登入頁 → 就緒）
3. 在該視窗選擇登入方式（Email 驗證碼／Continue with Google／Continue With Github）
4. 登入成功後程式會自動偵測並儲存 session，並關閉該視窗（**之後不必再登入**）
5. 回到「總覽」頁按「**立即簽到**」即可測試；成功後會顯示獲得的點數
6. 到「設定」頁設定每日自動簽到時間，並視需要開啟「開機自啓動」

**登入過程的錯誤提示**（不會讓你白等）：

| 狀況 | 提示 |
|---|---|
| 沒有網路／DNS 失敗 | 「無法連線」＋請檢查網路連線（**啟動瀏覽器前就先檢查**） |
| 代理伺服器問題 | 「代理伺服器問題」＋請檢查設定中的代理伺服器 |
| TLS／憑證錯誤 | 「憑證錯誤」＋可能是網路環境或代理攔截 |
| 連線逾時 | 「登入逾時」＋網路過慢或被阻擋 |
| 你關掉了瀏覽器視窗 | 「視窗已關閉」＋**立即**回報，不需等逾時 |
| 不想繼續 | 可隨時關閉視窗或取消，程式會立即停止等待（等待上限 5 分鐘） |
| 剛好在自動簽到 | 會先顯示「正在等待目前的簽到作業結束…」，待簽到完成才開啟登入視窗（避免兩者互相重啟瀏覽器） |
| 螢幕較小或縮放較大 | 登入視窗會自動最大化；若內容仍高於視窗，登入頁會**自動等比縮放**，確保最下方的登入選項都在畫面內 |
| 介面主題顏色不對 | 已修正：App 主題會強制覆寫 Qt 的 `colorScheme`，因此「淺色」不受 Windows 深色模式影響；設定切換後立即生效 |

## 常見問答

**Q：執行時會出現 CMD 黑窗嗎？**
不會。主程式與安裝程式都是 GUI 子系統（PE subsystem=2，已實測驗證）。
若你想看執行訊息，可執行 `run.bat --console`（僅開發模式）。

**Q：可以在沒有安裝 Chrome／Edge 的電腦上用嗎？**
可以。完整版安裝包已內建 Chromium，不需任何額外瀏覽器。
精簡版則會自動改用系統的 Chrome／Edge，或可在設定頁一鍵下載核心。

> 登入一律由使用者手動完成（本工具**不做驗證碼或風控繞過**）。

---

## 設定項目

**一般**：介面主題、開機自啓動、啟動時縮到系統匣、關閉視窗時縮到系統匣、只允許一個實例

**簽到**：每日執行時間（可選時／分）、隨機延遲（±0~180 分）、啟動時補簽、頁面逾時、
失敗重試次數／間隔、無頭模式、無頭失敗改用顯示視窗重試、執行後保留瀏覽器視窗

**帳號**：同時處理帳號數（1~3，建議 1）、加密儲存 session、開啟資料目錄、清除所有登入狀態

**通知**：簽到成功／失敗／需要重新登入時的系統通知

**進階**：瀏覽器核心（內建 Chromium／系統 Chrome／Edge）、代理伺服器、自訂 User-Agent、
日誌等級與保留天數、改版偵測門檻、日誌／診斷／專案資料夾

資料與設定位置：`%APPDATA%\MinimaxCheckin\`
（`config.json`、`accounts\`、`logs\`、`diagnostics\`、`state.json`）

---

## 運作原理（逆向研究摘要）

完整研究報告見 **[docs/research/findings.md](docs/research/findings.md)**。

1. **登入**：`account.minimax.io/unified-login` 走 OAuth2 授權碼流程，回呼到
   `agent.minimax.io/auth/callback`。登入後 token（JWT，約 40 天有效）存放於
   `localStorage._token`（同時存在 cookie `_token`），因此只要保存 Playwright
   `storage_state` 就能還原登入，**不需密碼**。
2. **簽到 API**：
   * `GET /minimax-cloud/api/v1/signin/status` → `days[].status`：`1` 未解鎖、`2` 今日可簽、`3` 已領取
   * `POST /minimax-cloud/api/v1/signin/claim`（body `{}`）→ `claim_result: 1`、`points`、`day_no`
3. **為何用瀏覽器而非純 HTTP**：官方 API 要求 `x-signature` / `yy` 等 MD5 簽章標頭，
   實測直接呼叫會回 `HTTP 400 {"error":"invalid signature"}`。因此本工具以
   **Playwright 操作真實 UI**（由官方前端自行帶上正確簽章），再用
   **攔截官方 API 回應**取得結構化結果 —— 免逆向簽章、又能精準判斷成敗。
4. **判斷流程**：載入頁面 → 攔截 `signin/status` → `status == 3` 直接判定今日已簽到（不點擊）；
   `status == 2` → 等待 `[data-testid="signin-card"]` 出現 → 點擊 `button.signin-claim-button`
   → 解析 `signin/claim` 回應 → 面板消失作為二次驗證。
5. **抗改版**：選擇器有版本（見 `app/constants.py` 的 `SELECTOR_PACK_VERSION`）並依序嘗試
   多個候選與文字特徵；連續失敗達門檻時提示應用可能過期，並可用 `tools/probe.py`
   重新掃描頁面產生新的選擇器資訊與診斷檔。

---

## 疑難排解

| 症狀 | 處理方式 |
|---|---|
| 顯示「需要重新登入」 | session 過期（token 約 40 天）→ 到「帳號」頁按「重新登入」 |
| 無頭模式簽不成功 | 關閉設定中的「無頭模式」（改用顯示視窗），或改「瀏覽器核心」為系統 Chrome；程式也會自動嘗試顯示視窗重試 |
| 提示「應用可能已過期」 | MiniMax 可能已改版 → 按「重新掃描頁面」，並參考 `docs/research/findings.md` 更新 `app/core/selectors.py` 後遞增 `SELECTOR_PACK_VERSION` |
| 想看簽到過程 | 設定 →「執行後保留瀏覽器視窗」＋關閉「無頭模式」 |
| 出現「點擊未成功」 | 通常是官方公告彈窗蓋住頁面（程式會自動關閉並重試）；若仍失敗，檢查診斷目錄的 `after_claim.png` |
| 程式關不掉 | 視窗 X 只會縮到系統匣；請用托盤圖示右鍵 →「結束」 |
| 想確認流程是否仍有效 | 執行 `.venv\Scripts\python.exe tools\verify_session.py --headed` |

## 改版維護流程

```bat
:: 1) 掃描目前頁面（輸出候選元素、指紋與截圖到 diagnostics 目錄）
.venv\Scripts\python.exe tools\probe.py --headed

:: 1b) 對真實站台跑一次完整簽到流程（今日已簽到時只會回報「已簽到」）
.venv\Scripts\python.exe tools\verify_session.py --headed

:: 2) 對照 docs/research/findings.md 的選擇器表，更新 app/core/selectors.py
::    （候選選擇器定義在 app/constants.py）

:: 3) 更新 tests/fixtures/*.html 並執行測試
.venv\Scripts\python.exe -m pytest

:: 4) 遞增 app/constants.py 的 SELECTOR_PACK_VERSION
```

## 專案結構

```
Minimax Check-in/
├─ main.py                     # 進入點（單一實例、--minimized）
├─ setup.bat / run.bat         # 安裝與啟動
├─ app/
│  ├─ config.py  paths.py  constants.py  logger.py
│  ├─ worker.py                # 背景執行緒（asyncio + Playwright）+ Qt 訊號
│  ├─ core/
│  │  ├─ browser.py            # 單一瀏覽器 + 每帳號隔離 context、互動登入擷取
│  │  ├─ checkin.py            # 簽到流程狀態機（攔截 API 回應做驗證）
│  │  ├─ selectors.py          # 選擇器引擎（多候選 + 文字啟發式 + 指紋）
│  │  ├─ engine.py             # 多帳號執行、結果彙總、改版計數
│  │  ├─ scheduler.py          # 每日排程 + 隨機延遲 + 補簽 + 重試
│  │  ├─ account.py  crypto.py # 帳號與 DPAPI 加密 session
│  │  ├─ state.py  autostart.py  diagnostics.py
│  └─ ui/
│     ├─ main_window.py        # FluentWindow + 左側導覽 + 標題列搜尋 + 系統匣
│     ├─ home_page.py / account_page.py / log_page.py / settings_page.py
│     ├─ components.py         # 自訂 Fluent 設定卡片與狀態元件
│     └─ icon.py               # 程式繪製的 App 圖示
├─ tools/probe.py              # 頁面重新掃描（改版時使用）
├─ tools/verify_session.py     # 對真實站台驗證簽到流程
├─ tests/                      # pytest（113 項，含實測 fixture）
└─ docs/research/findings.md   # 逆向研究報告（API／DOM／狀態語意）
```

## 測試

```bat
.venv\Scripts\python.exe -m pytest
```

涵蓋：選擇器引擎（以實測 HTML fixture 離線驗證）、API 回應解析、設定正規化與持久化、
DPAPI 加解密往返、帳號管理、簽到結果狀態機、排程時間與隨機延遲計算。

## 已知限制

* 需在 Windows 上執行（DPAPI 加密、開機自啓動、系統匣通知皆為 Windows 功能）
* 登入需使用者手動完成一次（不處理驗證碼）
* 點數規則（800／2,000 等）由 MiniMax 決定，本工具僅記錄與回報，不保證收益
* 若官方改為需要互動式人機驗證，無頭模式可能失效，請改用顯示視窗或系統 Chrome
* 自動化行為仍受官方風控政策約束，請自行評估使用風險並適度使用

## 授權與致謝

* 介面風格與技術棧參考 [Ghost Downloader 3](https://github.com/XiaoYouChR/Ghost-Downloader-3)（GPL-3.0）
* Fluent Design 元件庫：[PySide6-Fluent-Widgets](https://qfluentwidgets.com)（GPL-3.0）
* 本專案僅供個人學習與自動化研究使用

## 開發方式

* 本專案以 **Cline + AI 模型協作**開發：
  [Muse Spark](https://www.muse.com/) `muse-spark`（`cline/free-muse-spark-1.3`，contributor 免費額度）
  負責主要實作與除錯，[DeepSeek](https://www.deepseek.com/) `deepseek-v4.1-flash` 負責初版雛形。
* 開發心得：DeepSeek v4.1 相比上一代進步巨大，多模態讓它在看 UI 截圖時表現好很多，
  但不少地方是用輸出長度堆智力，容易一次造出一堆 bug；後來換 Muse Spark 把 bug 逐一修掉，
  才有現在這個穩定可用的版本。

