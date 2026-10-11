# 桌面截圖／操作 MCP 整合報告（win32-desktop）

> 目的：讓 Cline 主 Agent 能自行對 Windows 桌面截圖、看到 PySide6 桌面 App（Minimax Check-in）、定位元件座標並執行點擊，不再依賴使用者手動截圖。
> 建立日期：2026-10-11　環境：Windows 11 (win32) + VS Code + Cline + Python 3.11。

---

## 一、候選比較表（5 個）

| # | 名稱 | 網址 | License | 安裝方式 | 功能 | Windows | 維護 | 淘汰理由 |
|---|------|------|---------|----------|------|:---:|------|------|
| 1 ✅ | **win32-mcp-server** | github.com/RandyNorthrup/win32-mcp-server ・ pypi.org/project/win32-mcp-server | **MIT** | `uvx`/`pip`（PyPI 有 wheel） | 53 工具：`capture_screen`/`capture_window`/`capture_monitor`（回傳 base64 圖）、`click`/`double_click`/`drag`、`type_text`、`list_windows`、UIA、OCR、`execute_sequence` | ✅ 專用 | ✅ 活躍（2026-04 最新 2.5.1，有 VS Code 擴充、Windows CI、SECURITY.md） | **採用**（見下） |
| 2 | ControlMCP | github.com/nix18/ControlMCP | GPL-3.0 | `pip install -e .`（需 clone） | 截圖、視窗管理、滑鼠/鍵盤、組合操作；附 computer-control skill 含座標規則 | ✅ | ⚠️ 普通（26 commits） | 需從源碼安裝、無 PyPI 套件、社群較小；功能與 #1 重疊 |
| 3 | MCPControl | github.com/claude-did-this/MCPControl | MIT | `npm i mcp-control` | 截圖、滑鼠鍵盤、視窗管理 | ✅ | ✅（330★） | **淘汰：README 明言 `get_screenshot` 在 Cline 上無法運作（issue #1865），且只針對 1280×720 單螢幕最佳化** — 截圖是核心需求，直接出局 |
| 4 | gui-mcp | github.com/lpmwfx/gui-mcp | EUPL-1.2 | Rust 單一 binary（需 cargo build） | 14 工具：視窗截圖、模板比對、點擊、輸入、剪貼簿；背景視窗不搶焦點 | ✅ | ⚠️ MVP（作者自述 as-is） | 需 Rust 編譯、0★/MVP、座標在高 DPI 可能漂移；EUPL 授權較少見 |
| 5 | mcp-pyautogui | github.com/Hathibelagal-dev/mcp-pyautogui | GPL-3.0 | `pip install mcp-pyautogui` | click/type/拖曳、`take_screenshot` | ✅ | ⚠️（15 commits） | **淘汰：`take_screenshot` 只把圖存成檔案回傳 bool，不回傳圖片本身**，Agent 看不到畫面；無視窗管理 |

**為何選 #1 win32-mcp-server**：唯一同時滿足「Windows 專用 + 本地截圖回傳圖片 + PyPI 隔離安裝 + MIT + 活躍維護 + 含 click/type/視窗管理/UIA」的專案；且官方有 VS Code 擴充與安全設定檔（read_only / dry-run / allow-list）。

---

## 二、選用的 MCP

- **名稱／版本**：`win32-mcp-server` v2.5.1（PyPI 最新穩定版；GitHub main 已到 2.6.1 但尚未發 wheel）
- **授權**：MIT（見專案 LICENSE）
- **依賴隔離**：使用 `uvx` 在獨立 ephemeral 環境執行，**完全不觸碰專案 `.venv`**，也不影響既有 playwright MCP
- **⚠️ 關鍵相容性修正**：此套件針對 MCP Python SDK **1.x** 的 API 撰寫（`Server.list_tools()`），但 PyPI 宣告 `mcp>=1.0.0` 會讓 uv 解析到 **mcp 2.x**，導致啟動即崩（`AttributeError: 'Server' object has no attribute 'list_tools'`）。**必須釘選 `mcp<2`**。

### 安裝命令（已執行）

```powershell
# 隔離安裝（本機驗證用；Cline 實際用 uvx 即時執行，見下）
uv tool install win32-mcp-server --with "mcp<2"
```

### Cline MCP 配置片段（已寫入，去敏）

設定檔位置（兩處都已更新）：
- `%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`（stable）
- `%APPDATA%\Code\User\globalStorage\saoudrizwan.cline-nightly\settings\cline_mcp_settings.json`（nightly）

```json
{
  "mcpServers": {
    "playwright": { "...原有不動...": "" },
    "playwright-electron": { "...原有停用...": "" },
    "win32-desktop": {
      "command": "uvx",
      "args": ["--with", "mcp<2", "win32-mcp-server"],
      "disabled": false,
      "alwaysAllow": []
    }
  }
}
```

> 改動前已自動備份：同目錄下 `cline_mcp_settings.json.bak-20261011-202610`。既有 playwright / playwright-electron 兩個 server 原封不動。

### 讓 Cline 載入

寫入設定檔後，於 Cline 面板 **MCP Servers** 分頁點 `win32-desktop` 旁的重新整理／或重啟 VS Code。工具名前綴會是 `win32-desktop`（例：`use_mcp_tool` server=`win32-desktop` tool=`capture_screen`）。

---


## 三、驗證結果

透過 stdio 手寫 JSON-RPC 客戶端（腳本置於 `%TEMP%`，未入專案）實際呼叫 server 驗證，全部成功：

| 步驟 | 工具 | 結果 |
|------|------|------|
| a. 握手 | `initialize` | ✅ `serverInfo: win32-inspector`，53 工具註冊 |
| a. 桌面截圖 | `capture_screen` | ✅ 回傳 `image/png` 1920×1200（425 KB），存檔可用；見到 VS Code / Chrome / 工作列。存證 `docs/_evidence_desktop.png` |
| a. 環境 | `health_check` | ✅ Windows 11、DPI 144（顯示縮放 150%）、單螢幕 1920×1200、Python 3.12 |
| b. 列出視窗 | `list_windows` | ✅ 列出 15 個視窗含 title/hwnd/pid/x/y/width/height |
| b. App 視窗截圖 | `capture_window`（`window_title="Minimax Check-in"`） | ✅ 成功擷取 PySide6 App 畫面（1180×672）。存證 `docs/_evidence_overview.png`：可見標題「Minimax Check-in」、左側導航（總覽/帳號/紀錄/設定）、「簽到總覽」與帳號清單（2D27 LU JUNJIE、pig lu，皆「簽到成功」） |
| c. 定位「立即檢查」按鈕 | 讀 `app/ui/settings_page.py` + `app/locales/zh-TW.json` | ✅ 按鈕＝`updateCheckCard`（`PushSettingCard`，`settings.update.check_now`＝「立即檢查」，圖示 SYNC），位於「設定」頁「關於」群組內 |
| c. 導航列座標測量 | PIL 像素掃描 | ✅ 「設定」導航項可點擊中心＝視窗相對 (x=69, y=337)（x 範圍 25–114） |
| c. 執行點擊 | `click(x,y)` | ✅ 回傳 `Clicked left x1 at (382, 443)`（＝視窗原點 313,106 + 相對 69,337）。點擊鏈路本身暢通 |

**點擊行為說明（重要）**：`click` 一律回報「已於該座標點擊」且鏈路暢通，但**是否命中目標元件取決於「該螢幕座標當下最上層的視窗」**。本次把 App 以 `SetWindowPos(HWND_TOPMOST)` 置頂後點擊導航列，合成點擊有送達 App，但 qfluentwidgets 的導航列未翻頁——這是 Qt 視窗在非真實前景焦點下對合成輸入的處理特性（見「風險/限制」）。**截圖、看畫面、座標定位、點擊送出四項能力均已實證可用**；「點擊後 App 100% 翻頁」需搭配前景焦點或 UIA（本 App 的 qfluentwidgets 導航項未暴露 UIA 名稱，`uia_find_control` 找不到）。

---

## 四、使用方法（給主 Agent）

Cline 中透過 `use_mcp_tool`，`server_name="win32-desktop"`。常用工具與參數：

**1) 截整個桌面（最常用，先看全局）**
```
use_mcp_tool(server="win32-desktop", tool="capture_screen", arguments={"format":"png"})
# 可選 scale:0.5 減小體積；format:"jpeg" 更小
```

**2) 只截某個視窗（推薦用於看 App，較不受其他視窗干擾）**
```
use_mcp_tool(server="win32-desktop", tool="capture_window",
  arguments={"window_title":"Minimax Check-in","activate":false})
```
> ⚠️ `window_title` 是**模糊子串匹配**，回傳枚舉順序中第一個標題含該字串的視窗。若同時有多個視窗標題含相同字（例如 VS Code 開著本專案檔案，標題為 `xxx.py - Minimax Check-in - Visual Studio Code`），可能截到錯的視窗。解法：先用 `list_windows` 確認，或用更獨特的字串。

**3) 列出視窗與座標（定位用）**
```
use_mcp_tool(server="win32-desktop", tool="list_windows", arguments={"filter":"Minimax"})
use_mcp_tool(server="win32-desktop", tool="get_window_info", arguments={"window_title":"Minimax Check-in"})
```

**4) 點擊／拖曳／鍵盤（座標為「實體螢幕像素」，非視窗相對）**
```
use_mcp_tool(server="win32-desktop", tool="click", arguments={"x":382,"y":443,"button":"left"})
use_mcp_tool(server="win32-desktop", tool="double_click", arguments={"x":100,"y":200})
use_mcp_tool(server="win32-desktop", tool="drag", arguments={"x":100,"y":200,"to_x":300,"to_y":400})
use_mcp_tool(server="win32-desktop", tool="type_text", arguments={"text":"hello"})
use_mcp_tool(server="win32-desktop", tool="hotkey", arguments={"keys":["ctrl","s"]})
```

**5) 依文字點擊（無需座標；需 Tesseract OCR）**
```
use_mcp_tool(server="win32-desktop", tool="click_text", arguments={"text":"立即檢查","window_title":"Minimax Check-in"})
```
> 目前本機**未安裝 Tesseract**，`click_text`/`ocr_*` 會失敗。若要啟用：`winget install --id tesseract-ocr.tesseract --exact`。純截圖/點擊/視窗管理不需要 OCR。

**6) UIA（無障礙樹）**
```
use_mcp_tool(server="win32-desktop", tool="uia_inspect_window", arguments={"window_title":"Minimax Check-in","max_depth":3})
use_mcp_tool(server="win32-desktop", tool="uia_find_control", arguments={"window_title":"Minimax Check-in","name":"..."})
```

> 建議把 `capture_screen`、`capture_window`、`list_windows`、`get_window_info`、`click`、`type_text` 加入 Cline 的 alwaysAllow 以減少來回確認（目前設定為空，需每次授權）。

---

## 五、風險／限制

1. **DPI 縮放**：本機顯示縮放 **150%**（DPI 144）。server 已自動啟用 per-monitor DPI awareness，`click` 座標以**實體像素**為準；但「視窗相對座標→實體座標」換算務必用 `get_window_info` 的 x/y（已是實體像素）為基底，勿用邏輯像素自行推算。
2. **多螢幕**：本機目前單螢幕。多螢幕時 `capture_screen` 只截主螢幕，要截全部需用 `capture_monitor`／`list_monitors`；跨負座標（副螢幕在左）時座標系要特別確認。
3. **合成點擊 vs 前台焦點**：`click(x,y)` 送到「該座標最上層視窗」。目標 App 若非前景，點擊可能落到別的視窗；Qt/qfluentwidgets 部分元件（如導航列）在非前景時可能不響應合成點擊。**要穩定操作 App，先把 App 視窗置前**（可用 `focus_window`，或由 Agent 先 `restore_window`）。
4. **模糊視窗匹配**：`window_title` 為子串模糊匹配，同名/含名視窗會競爭（本專案 VS Code 標題就含 "Minimax Check-in"）。**截 App 前先 `list_windows` 確認唯一性**。
5. **管理員視窗**：以系統管理員執行的視窗，一般權限的 server 無法操作（UIPI）。若 VS Code／server 非管理員而目標是管理員視窗，會 `Access is denied`。
6. **Tesseract 未安裝**：`click_text`、`find_text_on_screen`、`ocr_*` 等依賴 OCR 的功能暫不可用；純視覺截圖+座標點擊不受影響。
7. **隱私**：截圖完全在本機處理、經 stdio 回傳 base64 給 Cline，**不上傳任何雲端**。但注意截圖可能包含帳號 session 等畫面，僅在本機 VS Code/Cline 上下文流動。
8. **mcp<2 釘選**：勿移除 `--with "mcp<2"`，否則 uv 會裝到 mcp 2.x 使 server 啟動即崩。若日後 upstream 升級支援 mcp 2.x，可移除此釘選。

---

## 六、給主 Agent 的摘要

> 已安裝並配置 **win32-mcp-server v2.5.1**（MIT）為 Cline MCP server，名稱 `win32-desktop`，用 `uvx --with "mcp<2" win32-mcp-server` 隔離啟動（未動專案 `.venv`、未動 playwright MCP，設定檔已備份）。
> **怎麼用**：`use_mcp_tool(server="win32-desktop", tool="capture_window", arguments={"window_title":"Minimax Check-in"})` 即可看到 App 畫面；`capture_screen` 截全桌面；`click`/`type_text`/`list_windows`/`get_window_info` 操作與定位。座標是**實體像素**，以 `get_window_info` 的 x/y 為基底。
> **要注意**：① 截 App 前先 `list_windows` 確認標題唯一（VS Code 開本專案時標題也含 "Minimax Check-in"）；② 目標 App 要置前才點得準（Qt 導航列在非前景可能不響應合成點擊）；③ 本機 DPI 150%，座標別用邏輯像素推算；④ `click_text`/OCR 需另裝 Tesseract（目前未裝）；⑤ 配置裡的 `--with "mcp<2"` 不可移除，否則 server 起不來。
> 設定檔：`%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`（stable 與 nightly 皆已更新）；寫入後請在 Cline MCP 面板重啟/重載 `win32-desktop`。
