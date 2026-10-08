"""單一實例喚醒通道：第二個行程叫出舊主視窗後靜默退出。

背景：舊行為是第二個行程彈「已在執行中」QMessageBox 就結束，
使用者還要自己去托盤找圖示。業界標準（Chrome／LINE）是第二個
發訊號給第一個叫出主視窗、自己安靜結束。

實作：Qt 原生 QLocalServer／QLocalSocket（不需新依賴，
pythonw／console=False 打包版皆可用）。Mutex 繼續負責防重複簽到，
此通道只負責「喚醒」。
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = "MinimaxCheckin-single-instance"
WAKE_MESSAGE = b"show"


class SingleInstanceWakeup(QLocalServer):
    """第一實例持有；收到喚醒訊息時發出 wakeRequested。"""

    wakeRequested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._listening = False
        # 清掉上次 crash 殘留的 pipe，否則 listen 會失敗
        QLocalServer.removeServer(SERVER_NAME)
        self._listening = bool(self.listen(SERVER_NAME))
        if self._listening:
            self.newConnection.connect(self._on_connection)

    @property
    def listening(self) -> bool:
        return self._listening

    def _on_connection(self) -> None:
        socket = self.nextPendingConnection()
        if socket is None:
            return
        state = {"done": False}

        def finish() -> None:
            if state["done"]:
                return
            state["done"] = True
            try:
                data = bytes(socket.readAll().data())
            except Exception:
                data = b""
            if WAKE_MESSAGE in data or not data:
                # 空訊息（僅連線）也視為喚醒，避免 client 只 connect 不寫入時無反應
                self.wakeRequested.emit()
            try:
                socket.disconnectFromServer()
            except Exception:
                pass
            socket.deleteLater()

        socket.readyRead.connect(finish)
        socket.disconnected.connect(finish)
        if socket.bytesAvailable() > 0 or socket.state() is not None:
            # 若資料已到達，排到事件迴圈處理（直接呼叫時 bytes 可能還沒備妥）
            from PySide6.QtCore import QTimer

            QTimer.singleShot(100, finish)


def wake_existing(timeout_ms: int = 2000) -> bool:
    """第二實例呼叫：嘗試喚醒已在執行的舊實例，成功回傳 True。

    連不上（舊行程已死／殘留 Mutex）回傳 False，呼叫端應 fallback 彈舊提示。
    """
    socket = QLocalSocket()
    try:
        socket.connectToServer(SERVER_NAME)
        if not socket.waitForConnected(timeout_ms):
            return False
        socket.write(WAKE_MESSAGE)
        socket.flush()
        socket.waitForBytesWritten(timeout_ms)
        socket.disconnectFromServer()
        return True
    except Exception:
        return False
    finally:
        try:
            socket.close()
        except Exception:
            pass
