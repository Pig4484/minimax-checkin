"""應用設定：dataclass 模型 + JSON 持久化。"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field, fields
from datetime import time
from pathlib import Path
from typing import Any

from app import paths
from app.constants import APP_VERSION

THEME_SYSTEM = "system"
THEME_LIGHT = "light"
THEME_DARK = "dark"

BROWSER_CHOICES = ("chromium", "chrome", "msedge")
BROWSER_LABELS = {
    "chromium": "內建 Chromium（免安裝）",
    "chrome": "系統 Google Chrome",
    "msedge": "系統 Microsoft Edge",
}
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


@dataclass
class AppConfig:
    """所有可調設定（GUI 設定頁即對應這些欄位）。"""

    version: str = APP_VERSION

    # --- 一般 ---
    theme: str = THEME_DARK
    autostart: bool = False
    start_minimized: bool = False
    close_to_tray: bool = True
    single_instance: bool = True
    minimize_on_launch_login: bool = True

    # --- 簽到 ---
    daily_time: str = "09:00"            # 每日執行時間 HH:MM
    jitter_minutes: int = 20             # 隨機延遲 ± 分鐘
    run_on_start_if_missed: bool = True  # 啟動時若今日未簽到則補簽
    retry_times: int = 2                 # 當日失敗重試次數
    retry_interval_minutes: int = 30     # 重試間隔
    timeout_seconds: int = 60            # 頁面/網路逾時
    headless: bool = True                # 無頭模式
    fallback_headed: bool = True         # 無頭失敗時改用顯示視窗重試
    keep_browser_open: bool = False      # 執行完保留瀏覽器視窗（除錯）

    # --- 帳號 ---
    concurrent_accounts: int = 1         # 同時處理帳號數（1~3）
    encrypt_sessions: bool = True        # 以 Windows DPAPI 加密 session

    # --- 通知 ---
    notify_success: bool = True
    notify_failure: bool = True
    notify_relogin: bool = True

    # --- 進階 ---
    browser_channel: str = "chromium"
    proxy: str = ""
    log_level: str = "INFO"
    log_days: int = 30
    drift_threshold: int = 3             # 連續幾次找不到介面 → 提示可能過期
    custom_user_agent: str = ""
    selector_pack_version: int = 0       # 執行時自動填入

    # ------------------------------------------------------------------
    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        path = path or paths.config_file()
        cfg = cls()
        if path.exists():
            try:
                raw: dict[str, Any] = json.loads(path.read_text("utf-8"))
            except Exception:
                raw = {}
            cfg = cls.from_dict(raw)
        return cfg

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AppConfig":
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in raw.items() if k in known}
        cfg = cls(**data)
        cfg.normalize()
        return cfg

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Path | None = None) -> None:
        path = path or paths.config_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(path)

    # ------------------------------------------------------------------
    def normalize(self) -> None:
        if self.theme not in (THEME_SYSTEM, THEME_LIGHT, THEME_DARK):
            self.theme = THEME_DARK
        if self.browser_channel not in BROWSER_CHOICES:
            self.browser_channel = "chromium"
        if self.log_level not in LOG_LEVELS:
            self.log_level = "INFO"
        self.jitter_minutes = max(0, min(180, int(self.jitter_minutes)))
        self.retry_times = max(0, min(10, int(self.retry_times)))
        self.retry_interval_minutes = max(1, min(720, int(self.retry_interval_minutes)))
        self.timeout_seconds = max(15, min(600, int(self.timeout_seconds)))
        self.concurrent_accounts = max(1, min(3, int(self.concurrent_accounts)))
        self.drift_threshold = max(1, min(30, int(self.drift_threshold)))
        self.log_days = max(1, min(365, int(self.log_days)))
        self._normalized_time()

    def _normalized_time(self) -> None:
        try:
            hh, mm = self.daily_time.split(":")
            hour, minute = int(hh), int(mm)
            assert 0 <= hour <= 23 and 0 <= minute <= 59
            self.daily_time = f"{hour:02d}:{minute:02d}"
        except Exception:
            self.daily_time = "09:00"

    @property
    def daily_time_obj(self) -> time:
        hour, minute = (int(x) for x in self.daily_time.split(":"))
        return time(hour=hour, minute=minute)

    def daily_jitter_minutes(self, seed: str) -> int:
        """同一 seed（日期）產生固定的隨機延遲，避免每天固定時間被風控。"""
        if self.jitter_minutes <= 0:
            return 0
        rng = random.Random(f"{seed}:{self.daily_time}")
        return rng.randint(-self.jitter_minutes, self.jitter_minutes)
