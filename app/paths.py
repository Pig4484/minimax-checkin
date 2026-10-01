"""集中管理檔案路徑。

遵循 Windows 應用程式慣例（與市面軟體一致）：

=============================  ==========================================================
位置                           內容
=============================  ==========================================================
``%APPDATA%\\MinimaxCheckin``   **設定檔**（Roaming，會隨使用者設定檔漫遊）
``%LOCALAPPDATA%\\…``          **本機資料**（Local）：帳號 session、日誌、診斷、執行狀態
``%LOCALAPPDATA%\\…\\browsers`` 執行期下載的瀏覽器核心（僅「精簡版」安裝需要）
=============================  ==========================================================

為什麼帳號 session 放 **Local** 而非 Roaming：session 以 Windows DPAPI 加密，金鑰綁定
「本機 + 目前使用者」，複製到別台電腦無法解密，放 Roaming 只會產生無用的同步資料。

支援 **可攜模式**：若執行檔旁存在 ``portable.flag``，或設定環境變數
``MINIMAXCHECKIN_PORTABLE=1``，所有資料改存於執行檔旁的 ``data`` 資料夾（不寫入 AppData）。
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from app.constants import APP_ID

PORTABLE_ENV = "MINIMAXCHECKIN_PORTABLE"
PORTABLE_FLAG = "portable.flag"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


# --- 執行檔／資源位置 ------------------------------------------------------
def is_frozen() -> bool:
    """是否為打包後的執行檔（PyInstaller）。"""
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    """原始碼專案根目錄（開發模式）。"""
    return Path(__file__).resolve().parent.parent


def install_dir() -> Path:
    """程式安裝目錄（開發模式下為專案根目錄）。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return project_root()


def bundled_dir() -> Path:
    """打包後的資源目錄（開發模式下等於專案根目錄）。"""
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else project_root()


def asset(*parts: str) -> Path:
    return bundled_dir() / "assets" / Path(*parts)


def bundled_browsers_dir() -> Path:
    """隨安裝檔附帶的瀏覽器核心（僅打包版存在）。"""
    return bundled_dir() / "ms-playwright"


def license_file() -> Path:
    return bundled_dir() / "LICENSE"


def notices_file() -> Path:
    return bundled_dir() / "THIRD-PARTY-NOTICES.md"


# --- 可攜模式 --------------------------------------------------------------
def is_portable() -> bool:
    if os.environ.get(PORTABLE_ENV) == "1":
        return True
    try:
        return (install_dir() / PORTABLE_FLAG).exists()
    except OSError:
        return False


def portable_root() -> Path:
    return ensure_dir(install_dir() / "data")


# --- 基礎目錄（Roaming / Local） -------------------------------------------
def _roaming_base() -> Path:
    if is_portable():
        return portable_root()
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / APP_ID


def _local_base() -> Path:
    if is_portable():
        return portable_root()
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / APP_ID


def roaming_dir() -> Path:
    """設定檔目錄（Roaming）。"""
    return ensure_dir(_roaming_base())


def local_dir() -> Path:
    """本機資料目錄（Local）。"""
    return ensure_dir(_local_base())


# --- 設定檔 ----------------------------------------------------------------
def config_file() -> Path:
    return roaming_dir() / "config.json"


# --- 本機資料 --------------------------------------------------------------
def accounts_dir() -> Path:
    return ensure_dir(local_dir() / "accounts")


def logs_dir() -> Path:
    return ensure_dir(local_dir() / "logs")


def diagnostics_dir() -> Path:
    return ensure_dir(local_dir() / "diagnostics")


def browsers_dir() -> Path:
    """執行期下載的瀏覽器核心（精簡版安裝）。"""
    return ensure_dir(local_dir() / "browsers")


def state_file() -> Path:
    return local_dir() / "state.json"


def app_file() -> Path:
    """單一實例鎖檔（舊版使用，僅用於清除殘留）。"""
    return local_dir() / ".lock"


# --- 相容舊版（資料原本全放在 Roaming） ------------------------------------
_LEGACY_DIRS = ("accounts", "logs", "diagnostics")
_LEGACY_FILES = ("state.json",)


def migrate_legacy() -> list[str]:
    """把舊版放在 Roaming 的執行期資料搬到 Local；設定檔留在 Roaming。

    回傳已搬移的項目（供日誌記錄）；任何錯誤都不會拋出例外。
    """
    moved: list[str] = []
    if is_portable():
        return moved
    legacy = _roaming_base()
    target = _local_base()
    if legacy == target:
        return moved

    for name in _LEGACY_DIRS:
        source_dir = legacy / name
        if not source_dir.is_dir():
            continue
        ensure_dir(target / name)
        for item in list(source_dir.iterdir()):
            destination = target / name / item.name
            try:
                if destination.exists() and item.is_file():
                    item.unlink()  # 目標已有同名檔 → 丟棄舊檔
                    moved.append(f"{name}/{item.name}（丟棄重複）")
                    continue
                shutil.move(str(item), str(destination))
                moved.append(f"{name}/{item.name}")
            except OSError:
                continue
        try:
            source_dir.rmdir()
        except OSError:
            pass

    for name in _LEGACY_FILES:
        source = legacy / name
        if not source.is_file():
            continue
        destination = target / name
        try:
            if destination.exists():
                source.unlink()
                moved.append(f"{name}（丟棄重複）")
            else:
                shutil.move(str(source), str(destination))
                moved.append(name)
        except OSError:
            pass

    for stale in (legacy / ".lock", target / ".lock"):
        if stale.exists():
            try:
                stale.unlink()
            except OSError:
                pass
    return moved


# --- 啟動命令 --------------------------------------------------------------
def gui_python() -> str:
    """開發模式下用於啟動的 Python（優先 pythonw，不彈黑窗）。"""
    if is_frozen():
        return sys.executable
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    return str(pythonw if pythonw.exists() else exe)


def launch_command() -> str:
    """開機自啓動要寫入登錄檔的完整命令列。"""
    if is_frozen():
        return f'"{sys.executable}" --minimized'
    entry = project_root() / "main.py"
    return f'"{gui_python()}" "{entry}" --minimized'
