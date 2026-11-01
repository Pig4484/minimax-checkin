"""網路可用性檢查。

簽到需要連線到 agent.minimax.io；在離線時若仍嘗試執行，Playwright 會整串失敗並
觸發一堆通知。因此排程器與手動執行前先做輕量的 TCP 探測，離線時直接跳過。
"""

from __future__ import annotations

import socket
from urllib.parse import urlparse


def is_online(proxy: str = "", host: str = "agent.minimax.io", port: int = 443, timeout: float = 3.0) -> bool:
    """以 TCP 連線探測網路是否可用（不發送 HTTP，避免觸發風控）。"""
    target_host, target_port = host, port
    if proxy:
        try:
            parsed = urlparse(proxy if "://" in proxy else "http://" + proxy)
            if parsed.hostname:
                target_host, target_port = parsed.hostname, parsed.port or 8080
        except Exception:
            pass
    try:
        with socket.create_connection((target_host, target_port), timeout=timeout):
            return True
    except OSError:
        # proxy 設定可能錯誤／不可達，退回直接探測目標站台
        if proxy:
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    return True
            except OSError:
                return False
        return False
