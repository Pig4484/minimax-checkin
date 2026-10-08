"""單例喚醒測試 helper（子行程執行，避免污染 pytest 主行程的 Qt 狀態）。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtNetwork import QLocalServer
from PySide6.QtWidgets import QApplication

from app.single_instance import SERVER_NAME, SingleInstanceWakeup, wake_existing


def roundtrip() -> int:
    app = QApplication([])
    server = SingleInstanceWakeup()
    if not server.listening:
        print("LISTEN-FAIL")
        return 1
    got: list[bool] = []
    server.wakeRequested.connect(lambda: got.append(True))
    if not wake_existing(timeout_ms=3000):
        print("WAKE-FAIL")
        return 1
    loop = QEventLoop()
    QTimer.singleShot(2000, loop.quit)
    server.wakeRequested.connect(loop.quit)
    if not got:
        loop.exec()
    server.close()
    app.quit()
    if got:
        print("ROUNDTRIP-OK")
        return 0
    print("SIGNAL-FAIL")
    return 1


def no_server() -> int:
    app = QApplication([])
    QLocalServer.removeServer(SERVER_NAME)
    ok = wake_existing(timeout_ms=500) is False
    app.quit()
    if ok:
        print("NO-SERVER-OK")
        return 0
    print("UNEXPECTED-WAKE")
    return 1


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "roundtrip"
    raise SystemExit(roundtrip() if mode == "roundtrip" else no_server())
