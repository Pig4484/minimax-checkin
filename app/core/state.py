"""每日執行狀態（避免重複簽到、支援當日重試）。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from app import paths


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class DayRunState:
    """當日執行狀態。"""

    date: str = ""
    attempts: int = 0
    last_attempt_at: str = ""
    last_reason: str = ""
    last_finished_at: str = ""
    all_ok: bool = False
    last_result: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "DayRunState":
        known = {f for f in cls().to_dict()}
        return cls(**{k: v for k, v in raw.items() if k in known})


class RunStateStore:
    """`state.json` 的讀寫。"""

    def __init__(self) -> None:
        self._path = paths.state_file()
        self.state = self.load()

    def load(self) -> DayRunState:
        if self._path.exists():
            try:
                return DayRunState.from_dict(json.loads(self._path.read_text("utf-8")))
            except Exception:
                pass
        return DayRunState()

    def save(self) -> None:
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.state.to_dict(), ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(self._path)

    # ------------------------------------------------------------------
    def reset_for_today(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        if self.state.date != today:
            self.state = DayRunState(date=today)
            self.save()

    def mark_attempt(self, reason: str) -> None:
        self.reset_for_today()
        self.state.attempts += 1
        self.state.last_attempt_at = now_text()
        self.state.last_reason = reason
        self.save()

    def mark_finished(self, all_ok: bool, summary: str) -> None:
        self.reset_for_today()
        self.state.all_ok = all_ok
        self.state.last_result = summary
        self.state.last_finished_at = now_text()
        self.save()

    @property
    def ran_today(self) -> bool:
        return self.state.date == datetime.now().strftime("%Y-%m-%d") and self.state.attempts > 0

    @property
    def last_attempt_datetime(self) -> datetime | None:
        try:
            return datetime.strptime(self.state.last_attempt_at, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None
