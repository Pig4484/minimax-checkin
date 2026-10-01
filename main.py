"""MiniMax Agent 自動簽到工具 — 程式進入點。

用法::

    python main.py               # 啟動 GUI
    python main.py --minimized   # 啟動後縮到系統匣（開機自啓動使用）
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme, setThemeColor

from app import logger as app_logger
from app import paths
from app.config import THEME_DARK, THEME_LIGHT, THEME_SYSTEM, AppConfig
from app.constants import APP_ID, APP_NAME, APP_VERSION, ORG_NAME
from app.core import diagnostics
from app.ui.icon import app_icon
from app.ui.components import sync_qt_color_scheme
from app.ui.main_window import MainWindow
from app.worker import AutomationWorker

ACCENT = "#0a84ff"
MUTEX_NAME = "MinimaxCheckin.SingleInstance"


def acquire_single_instance():
    """以 Windows 具名 Mutex 確保只有一個實例。

    行程結束（含被強制結束）時系統會自動釋放 Mutex，因此不會像鎖檔那樣留下殘留狀態。
    回傳 handle 表示取得成功；回傳 None 表示已有其他實例正在執行。
    """
    try:
        import win32api
        import win32event
        import winerror

        handle = win32event.CreateMutex(None, False, MUTEX_NAME)
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            return None
        return handle
    except Exception:  # pywin32 不可用時不阻擋啟動
        return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} {APP_VERSION}")
    parser.add_argument("--minimized", action="store_true", help="啟動後直接縮到系統匣")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    holder: dict[str, Any] = {"app": None}
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORG_NAME)
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)
    holder["app"] = app

    cfg = AppConfig.load()

    # 早期版本使用 QLockFile 鎖檔，若有殘留會誤判成「已在執行」，直接清除
    stale_lock = paths.app_file()
    if stale_lock.exists():
        try:
            stale_lock.unlink()
        except OSError:
            pass

    instance = acquire_single_instance() if cfg.single_instance else True
    if instance is None:
        # 注意：此時日誌系統尚未初始化，且 pythonw 下沒有主控台，
        # 因此直接彈窗告知（而不是只 print／寫 log，否則使用者完全看不到）。
        try:
            from PySide6.QtWidgets import QMessageBox

            box = QMessageBox()
            box.setIcon(QMessageBox.Information)
            box.setWindowTitle(APP_NAME)
            box.setText(f"{APP_NAME} 已在執行中。")
            box.setInformativeText("程式已縮到系統匣（工作列右下角 ^ 圖示區），雙擊托盤圖示即可叫回主視窗。")
            box.exec()
        except Exception:
            pass
        return 0

    theme_map = {THEME_DARK: Theme.DARK, THEME_LIGHT: Theme.LIGHT, THEME_SYSTEM: Theme.AUTO}
    setTheme(theme_map.get(cfg.theme, Theme.DARK))
    setThemeColor(ACCENT)
    sync_qt_color_scheme()

    worker = AutomationWorker(cfg)

    def gui_sink(message: str) -> None:
        level, _, rest = message.partition("|")
        stamp, _, text = rest.partition("|")
        worker.logMessage.emit(level.strip() or "INFO", f"{stamp}  {text}".strip())

    def show_crash(message: str, log_path) -> None:
        """發生未預期錯誤時彈出視窗告知使用者（而非無聲結束）。"""
        if holder["app"] is None:
            return
        try:
            from PySide6.QtWidgets import QMessageBox

            box = QMessageBox()
            box.setIcon(QMessageBox.Critical)
            box.setWindowTitle(f"{APP_NAME} — 發生錯誤")
            box.setText("程式發生未預期錯誤。")
            box.setInformativeText(
                f"{message}\n\n詳細記錄：{log_path or '（無法寫入記錄檔）'}"
            )
            box.exec()
        except Exception:
            pass

    app_logger.enable_utf8_console()
    try:
        app_logger.setup(cfg.log_level, cfg.log_days, gui_sink=gui_sink)
    except Exception as exc:  # 記錄檔寫入失敗仍應能啟動
        print(f"日誌初始化失敗（將繼續執行）：{exc}")
    logger = app_logger.logger
    app_logger.install_crash_handler(show_crash)

    logger.info(f"{APP_NAME} v{APP_VERSION} 啟動中…")
    moved = paths.migrate_legacy()
    if moved:
        logger.info(f"已從舊版資料夾搬移 {len(moved)} 個項目到本機資料目錄")
    logger.info(f"設定檔目錄（Roaming）：{paths.roaming_dir()}")
    logger.info(f"本機資料目錄（Local）：{paths.local_dir()}{'（可攜模式）' if paths.is_portable() else ''}")
    diagnostics.prune(20)

    window = MainWindow(cfg, worker)
    worker.start()

    # --minimized 是開機自啓動／背景啟動專用（登錄檔命令自帶此旗標）。
    # 一般手動雙擊啟動一律顯示主視窗；「啟動時縮到系統匣」只影響開機自啓動那一次。
    if args.minimized:
        window.hide()
    else:
        window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
