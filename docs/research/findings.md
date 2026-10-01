# MiniMax Agent 每日簽到 — 逆向研究報告

> 研究日期：2026-09-28｜方法：Playwright（真實 Chrome，非 headless）實測 + 網路擷取 + DOM 擷取
> 對應程式：`app/constants.py`（`SELECTOR_PACK_VERSION = 1`）

## 1. 站台與登入

| 項目 | 內容 |
|---|---|
| 站台 | `https://agent.minimax.io/`（前端代號 `mavis`） |
| 登入授權 | OAuth2 授權碼流程，`client_id=agent-minimax` |
| 登入頁 | `https://account.minimax.io/unified-login?login_redirect=...` |
| 回呼 | `https://agent.minimax.io/auth/callback` |
| 登入方式 | Email（OTP 驗證碼）／Continue with Google／Continue With Github |

### 登入後的憑證存放位置

- `localStorage._token`：JWT（**同時**也寫入 cookie `_token`）；有效期約 **40 天**，每次進站會由 `POST /v1/api/user/renewal` 自動續期
- `localStorage.user_detail_agent`：`{"userID":"WP8eDWvbWvzm","realUserID":"520369198996369411","userName":"...","accountAvatarUrl":"..."}`
- `localStorage.UNIQUE_USER_ID`：裝置/瀏覽器 UUID（同時作為 API 的 `uuid` query 參數）
- cookie：`_token`、`_twpid`、`_twsid` 等

→ **結論：只要保存 Playwright `storage_state`（cookies + localStorage）即可完整還原登入，不需密碼、不需重複登入。**（每個帳號一份 storage_state，即可在同一瀏覽器內以不同 context 隔離多帳號）

### 登入狀態判定（DOM）

- 未登入：`button[data-testid="sidebar-signed-out-login"]`
- 已登入：頁面出現 `[data-testid="sidebar-user-menu-trigger"]`、`localStorage._token` 存在
- 若被導向 `account.minimax.io/unified-login` → 需要重新登入

## 2. 簽到 API（核心）

| 用途 | 請求 |
|---|---|
| 簽到狀態 | `GET https://agent.minimax.io/minimax-cloud/api/v1/signin/status` |
| 執行簽到 | `POST https://agent.minimax.io/minimax-cloud/api/v1/signin/claim`，body = `{}` |
| 簽到設定/獎勵（標題、背景圖） | `GET /minimax-cloud/api/v1/signin/config` |
| 使用者資訊 | `GET /v1/api/user/info` |
| Token 續期 | `POST /v1/api/user/renewal` |
| 點數 | `GET https://platform.minimax.io/backend/account/token_plan_credit` |

**必要標頭**：`token`(JWT)、`x-timestamp`、`x-signature`、`yy`；query 需帶 `device_platform=web,biz_id=3,app_id=3001,version_code=22201,unix,timezone_offset,lang,sys_language,uuid,device_id,os_name,browser_name,screen_width,screen_height,user_id,token,client=web`

**⚠️ 簽章強制**：實測以 `fetch` 直接呼叫（帶 token、帶 cookie）皆回 `HTTP 400 {"error":"invalid signature"}`。
→ **本專案不偽造簽章**，改採「Playwright 操作真實 UI + 攔截網站自己發出的 API 回應」策略：既不用逆向簽章，又能取得結構化資料。

### `signin/status` 回應與狀態語意

```json
{"data":{"scene":4,"days":[
  {"day_no":1,"points":800,"bonus_points":400,"status":2,"is_today":true},
  {"day_no":2,"points":800,"bonus_points":400,"status":1,"is_today":false},
  {"day_no":3,"points":800,"bonus_points":400,"status":1,"is_today":false},
  {"day_no":4,"points":2000,"bonus_points":1000,"status":1,"is_today":false},
  {"day_no":5,"points":800,"bonus_points":400,"status":1,"is_today":false},
  {"day_no":6,"points":800,"bonus_points":400,"status":1,"is_today":false},
  {"day_no":7,"points":2000,"bonus_points":1000,"status":1,"is_today":false}
]},"base_resp":{"status_code":0,"status_msg":"ok"}}
```

| `days[].status` | 語意 |
|---|---|
| `1` | 尚未解鎖（未來天數） |
| `2` | **今日可簽（尚未領取）** |
| `3` | **已領取** |

- `is_today: true` 標記今天的位置
- 判定：`today.status == 3` → 今日已簽到；`== 2` → 需要簽到

### `signin/claim` 回應

```json
{"data":{"panel":{"scene":2,"days":[{"status":3,"is_today":true,...}]},
  "claim_id":"2104563840850071839","claim_result":1,"day_no":1,
  "points":800,"expire_at_ms":1793116800000},
 "base_resp":{"status_code":0,"status_msg":"ok"}}
```

- 成功判定：`base_resp.status_code == 0` 且 `claim_result == 1`
- 獲得點數：`points`；`expire_at_ms` 為點數到期時間（約 30 天）

## 3. DOM 結構（已實測擷取）

| 元素 | 選擇器 |
|---|---|
| 面板容器 | `[data-testid="signin-card"]`（class `signin-card-container`，內層 `.signin-card-surface`） |
| 標題 | `h2` = `Daily check-in` |
| 副標 | `p` = `Check in consecutively to earn more Credits` |
| 第 N 天圓點 | `[data-testid="signin-day-N"]`（N=1..7），class `signin-day text-text_default_accent`（今日）／`text-text_default_tertiary`（未到） |
| 第 N 天獎勵 | `[data-testid="signin-day-reward-N"]`（class `signin-day-points`，文字 `800`／`2,000`） |
| 加成標籤 | `[data-testid="signin-bonus"]`（class `signin-bonus-tag`，文字 `ADD400`） |
| **主簽到按鈕** | **`button.signin-claim-button`**，`aria-label="Check in for 800 Credits"`，文字 `Check in for800`，未簽到時 `disabled=false` |
| 關閉鈕 | `button[aria-label="Close check-in"]` |
| 說明鈕 | `button[aria-label="About check-in Credits"]` |

### 觀察到的狀態差異

| 狀態 | 面板 | 按鈕 | `status` |
|---|---|---|---|
| 今日可簽 | 存在 | `.signin-claim-button`（enabled，aria `Check in for N Credits`） | 2 |
| 今日已簽到 | **完全不渲染**（`signin-card` 不存在，DOM 中無任何 `signin` 元素） | 無 | 3 |

## 4. 建議的自動化流程（本專案實作）

1. 以帳號的 `storage_state` 開新 context（隔離 cookie）
2. `goto https://agent.minimax.io/`，同時以 `expect_response` 監聽 `**/signin/status`
3. 若被導向登入頁 → `NEED_RELOGIN`（不重試，通知使用者）
4. 取得 status：
   - 今日 `status == 3` → `ALREADY`（今日已簽到，**不點擊**）
   - 今日 `status == 2` → 等 `[data-testid="signin-card"]` 出現 → 找 `.signin-claim-button` → 點擊（同時 `expect_response` 監聽 `**/signin/claim`）
   - 取得 claim 回應 → `claim_result == 1` → `SUCCESS`（記錄 `points`、`day_no`）
5. 二次驗證：確認面板消失（或 status 轉為 3）
6. 找不到 status 回應或找不到面板／按鈕 → `DRIFT`（記錄診斷檔，連續 N 次 → 提示「應用版本可能過期」）

## 5. 會被攔截點擊的彈窗（2026-09-29 實測重現）

官方在部分情況下會顯示全頁公告彈窗，**蓋住整個頁面並攔截 pointer events**，導致簽到按鈕點不到
（Playwright `click()` 會一直重試到逾時）：

```html
<div role="dialog" aria-modal="true" aria-label="The Latest MiniMax Code Update Is Here."
     class="fixed inset-0 z-[1001] z-[9999] bg-utility_overlay">
  ...
  <button aria-label="Close">Close</button>
  <button>Try it now</button>
</div>
```

處理方式（`app/core/checkin.py`）：

1. 簽到前先呼叫 `_dismiss_overlays()`：尋找 `[role="dialog"][aria-modal="true"]`、
   `[aria-modal="true"]`、`div.bg-utility_overlay`
2. 依序嘗試：彈窗的關閉鈕（`button[aria-label*="Close"]` 等）→ 按 `Escape`
   → 直接以 JS 移除遮罩節點（純 UI 元素，不影響簽到請求）
3. 點擊失敗時會自動關閉遮罩並重試（最多 3 次），最後手段為 `locator.dispatch_event("click")`

> 回歸測試：`tests/test_overlays.py`（fixture：`tests/fixtures/blocking_modal.html`）

## 6. 互動登入流程（2026-09-29 改版）

### 目標行為

按下「新增帳號／重新登入」後，**直接停在官方的登入頁**，讓使用者選擇登入方式：

```
啟動瀏覽器（顯示視窗，最大化）
   ↓
載入 https://agent.minimax.io/
   ↓
點擊 [data-testid="sidebar-signed-out-login"]（官方自行產生 OAuth 參數）
   ↓
https://account.minimax.io/unified-login?login_redirect=%2Foauth2%2Fauthorize...
   （Welcome to MiniMax｜Enter your email｜Continue｜Continue with Google｜Continue With Github）
   ↓
偵測已登入（頁面回到 agent.minimax.io 且 localStorage 有合法 JWT）→ 儲存 storage_state
```

### 實作要點與實測數據

| 項目 | 說明 |
|---|---|
| 等待按鈕渲染 | 必須 `wait_for_selector` 等 `sidebar-signed-out-login` 出現；`domcontentloaded` 時前端尚未 hydrate，直接找按鈕會失敗 |
| 遮擋處理 | 點擊前先移除 `[aria-modal="true"]` / `div.bg-utility_overlay`（公告彈窗會攔截點擊） |
| 失敗退路 | 一般 `click()` 失敗時改用 `dispatch_event("click")` |
| 視窗尺寸（第一版修正） | 實測螢幕 1280×800、縮放 150%：舊版固定 `viewport=1440×900` → 需要 2160 實體像素而**被裁切**；改為顯示模式 `--start-maximized` + `no_viewport=True` |
| **視窗最大化** | `--start-maximized` 在部分環境（多螢幕／DPI 縮放／由無主控台行程啟動）可能失效 → 以 **CDP `Browser.setWindowBounds {windowState: maximized}`** 明確設定並驗證 |
| **頁面自動縮放** | 即使最大化，高 DPI 螢幕可用高度仍可能不足（1920×1200 @150% → 僅 665 CSS px）。登入頁就緒後量測 `scrollHeight` vs `innerHeight`，必要時注入 `html { zoom: N }`（下限 60%），確保最底部元素也在畫面內 |
| **與簽到互斥** | 簽到（headless）與登入（headed）若交錯，會互相把瀏覽器重啟、打斷對方。加入長期操作鎖 `browser.operation`：整輪簽到與互動登入不可同時進行，登入會先顯示「正在等待目前的簽到作業結束…」 |
| 實測結果 | `windowState=maximized`、視窗 1296×768、`innerHeight=665`、最底部元素（Privacy Policy）`bottom=595` → **內容完整可見** ✅ |
| 階段回報 | `launching`（啟動瀏覽器）→ `opening`（連線／開登入頁）→ `fitting`（調整顯示範圍）→ `ready`（登入頁就緒）→ `success`／`failed` |
| 網路預檢 | 啟動瀏覽器前先以 socket 連 `agent.minimax.io:443`（6 秒逾時），失敗立即回報，不浪費使用者時間 |
| 錯誤分類 | `network` / `proxy` / `ssl` / `timeout` / `blocked` / `closed` / `cancelled` / `no_browser` → 各自對應中文說明與通知標題 |
| 即時偵測 | 監聽 `page.on("close")` 與 `context.on("close")`，使用者關掉視窗 → 立刻回報「登入視窗已關閉」 |
| 可取消 | GUI 可送出取消訊號；等待迴圈每秒檢查，立即中止 |
| 逾時 | 由原本 900 秒縮短為 **300 秒**（`LOGIN_TIMEOUT_SECONDS`），避免卡住後續操作 |
| 效能 | 啟動時**不再預先開啟無頭瀏覽器**（改為需要時才啟動），登入只需啟動一次顯示視窗；實測從按下到「登入頁就緒」約 **5 秒** |

### 實測驗證（自動化）

```
[launching] 正在啟動瀏覽器視窗…
[opening]   正在連線 MiniMax…
[opening]   正在開啟登入頁面…
  登入頁資訊: {'url': 'https://account.minimax.io/unified-login?...',
              'w': 1280, 'h': 665, 'dpr': 1.5, 'hasEmail': True, 'hasGoogle': True}
[ready]     登入頁面已就緒，請在瀏覽器視窗完成登入
→ 使用者取消 → error: cancelled（立即回報）
```

## 7. 環境相容性實測

- Playwright（Chromium 153）＋ `args=["--disable-blink-features=AutomationControlled"]`、`ignore_default_args=["--enable-automation"]` → `navigator.webdriver === false`，頁面正常載入
- 目標站未觀察到 Cloudflare/驗證碼阻擋（登入階段由使用者手動完成）
- headless 模式測試：**頁面可正常載入與取得標題**；實際簽到流程若遇風控，程式會自動降級為顯示視窗模式重試

## 7. 介面主題（淺色／深色）修正（2026-10-01）

### 症狀

淺色主題下出現「標題列與左側導覽是淺色、但內容區仍是深色」的詭異外觀，
標題文字（深色字）在深色背景上幾乎看不見。

### 根因

**Qt 6.8+ 的 `QStyleHints.colorScheme()` 預設跟隨 Windows 系統設定**。
開發機的 Windows 是深色模式，因此：

* `qfluentwidgets.setTheme(Theme.LIGHT)` 只換掉它自己管理的元件（導覽列、標題列、卡片）
* 但 `SmoothScrollArea` 的 viewport、以及 `StatCard` 等使用 **Qt 原生調色盤**繪製的區域
  仍套用系統深色 → 內容區維持 `#1e1e1e`

實測數據（修正前）：

| 項目 | 淺色主題 | 深色主題 |
|---|---|---|
| `isDarkTheme()` | False ✅ | True ✅ |
| 內容區背景 | `#1e1e1e` ❌ | `#1e1e1e` ✅ |
| 統計卡片 | `#b4b4b4`（半透明白疊深底） | `#292929` ✅ |

### 修正

1. `app/ui/components.py::sync_qt_color_scheme()`：切換主題時同步設定
   `QStyleHints.setColorScheme(Light/Dark)`，讓 Qt 原生繪製的元件跟隨 App 主題而非系統
2. `app/ui/components.py::make_background_transparent()`：將四個頁面
   （`homePage` / `accountPage` / `logPage` / `settingsPage`）與其 viewport 設為透明，
   顏色完全交給 qfluentwidgets 的主題背景
3. `main.py` 與 `MainWindow._apply_theme()` 都會呼叫 `sync_qt_color_scheme()`

實測結果（修正後）：

| 項目 | 淺色主題 | 深色主題 |
|---|---|---|
| `colorScheme` | Light ✅ | Dark ✅ |
| 內容區背景 | `#ffffff` ✅ | `#2c2c2c` 🎉 |
| 統計卡片 | `#ffffff` ✅ | `#292929` ✅ |

> 回歸測試：`tests/test_theme.py`

## 8. 登入頁自動縮放（2026-10-01 強化）

即使視窗已最大化，高 DPI 螢幕的可用高度仍可能不足，導致登入頁最下方的
「Continue With Github」與條款同意被切掉。

修正後的邏輯（`BrowserManager._fit_page_to_window`）：

1. 量測**最底部元素的 `getBoundingClientRect().bottom`**（比 `scrollHeight` 準確，
   且能正確反映 CSS `zoom`）
2. 若溢出，套用 `html { zoom: N }`，並**重新量測、迭代調整**（最多 4 次，
   最小值 65%），確保內容真的完整可見
3. 每次迭代以「目前已套用的縮放」為基準計算，避免過度縮小

實測（刻意把視窗縮到 1100×620 模擬小視窗）：

```
縮小後 innerH=638
套用縮放 = 0.96
縮放後: innerH=638 bottomMost=561 zoom=0.96 fits=True
最後按鈕: Continue / Continue with Google / Continue With Github(bottom=520)
提示：登入頁面已就緒…（已自動縮放至 96% 以完整顯示）
```

## 9. 打包細節：不會出現 CMD 黑窗（2026-10-01 驗證）

| 產物 | PE subsystem | 結果 |
|---|---|---|
| `MinimaxCheckin.exe` | 2 | **GUI，無主控台** ✅ |
| `MiniMaxCheckin-Setup-1.0.0-full.exe` | 2 | **GUI，無主控台** ✅ |

* PyInstaller spec 設 `console=False`
* 安裝精靈以 `/VERYSILENT` 執行時不會開視窗；正常安裝為圖形精靈
* 卸載時呼叫 `taskkill` 的動作使用 `Flags: runhidden`，不會閃出黑窗
* 程式內部亦已處理「無主控台時 `sys.stderr is None`」的情形（loguru 跳過 console sink）

## 8. 主題與視窗尺寸修正（2026-10-01）

### 症狀

* 淺色主題下「標題列／導覽列是淺色，但內容區仍是深色」，標題幾乎看不見
* 深色主題若改成透明，則內容區反而變成淺色
* 視窗可被縮到很小，導致內容被裁切、左側導覽列被自動收合

### 根因（三個原因疊加）

1. **Qt 6.8+ 自動跟隨 Windows 系統配色**：`QStyleHints.colorScheme()` 預設等於系統設定。
   開發機的 Windows 是深色模式，因此 `qfluentwidgets.setTheme(LIGHT)` 只換掉它自己管理的元件
   （導覽列、標題列），而 `SmoothScrollArea` 的 viewport 與卡片仍使用 Qt 原生調色盤 → 維持深色。
2. **Mica 半透明材質**：`FluentWindow.setMicaEffectEnabled(True)` 會讓底層材質（跟隨系統色）
   透過半透明區域顯示出來，因此即使 App 主題正確，內容區底色仍可能被系統色干擾。
3. **沒有最小視窗尺寸**：使用者把視窗縮到很窄時，統計卡片被裁切、導覽列自動收合成只剩圖示。

實測數據（修正前 → 修正後）：

| 項目 | 淺色（修正前） | 淺色（修正後） | 深色（修正前） | 深色（修正後） |
|---|---|---|---|---|
| `colorScheme` | Dark ❌ | Light ✅ | Dark ✅ | Dark ✅ |
| 內容區背景 | `#1e1e1e` ❌ | `#f3f3f3` ✅ | `#ffffff` ❌ | `#1c1c1c` ✅ |
| 最小視窗尺寸 | 無 | 940×620 | 無 | 940×620 |

### 修正

1. `sync_qt_color_scheme()`：切換主題時同步 `setColorScheme()`，讓 Qt 原生繪製的元件跟隨 **App 主題**（非系統）
2. `make_background_transparent()` → 改為**明確指定不透明的主題實色**
   （深色 `#1c1c1c`／淺色 `#f3f3f3`），不再設為 `transparent`（避免透出底層材質）
3. `refresh_page_backgrounds()`：主題切換後即時把背景色套回四個頁面
4. `setMicaEffectEnabled(False)`：關閉 Mica 半透明材質
5. `setMinimumSize(940, 620)`：視窗不可被縮到無法使用

> 回歸測試：`tests/test_theme.py`（含主題色、Mica 關閉、最小尺寸三項斷言）

### 瀏覽器視窗「導航後被重置」的處理

實測發現 Chromium 有時會在**首次導航後**把視窗還原成建立時的尺寸，
使得「導航前最大化」失效。現在在**導航前後各執行一次**最大化，並改為
「讀取邊界 → 若偏小則要求 maximized → 重新讀取驗證（最多 3 次）」：

```
[launching] 正在啟動瀏覽器視窗…
_maximize_window = True          ← 導航前
[opening]   正在開啟登入頁面…
_maximize_window = True          ← 導航後（對抗 Chromium 重置）
[fitting]   正在調整登入頁面顯示範圍…
[ready]     登入頁面已就緒（已自動縮放至 97% 以完整顯示）
```

> 回歸測試：`tests/test_login_flow.py`（最大化、no_viewport、自動縮放、操作鎖）

## 8. 保養建議（官方改版時）

1. 執行 `python tools/probe.py`（或以 GUI「重新掃描頁面」）重新擷取 DOM/API
2. 對照本文件的選擇器表，更新 `app/core/selectors.py` 與 `app/constants.py`
3. 遞增 `SELECTOR_PACK_VERSION` 並補充/更新 `tests/fixtures/` 的 HTML fixture
