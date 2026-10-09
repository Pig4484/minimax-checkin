"""帳號模型與多帳號 session（storage_state）管理。"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from typing import Any

from app import paths
from app.core import crypto


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_text() -> str:
    return datetime.now().strftime("%Y-%m-%d")


@dataclass
class Account:
    id: str = ""
    alias: str = ""
    enabled: bool = True
    created_at: str = ""
    user_name: str = ""
    user_id: str = ""
    avatar: str = ""
    last_login_at: str = ""
    last_run_at: str = ""
    last_checkin_date: str = ""
    last_status: str = ""
    last_message: str = ""
    last_points: int = 0
    total_points: int = 0
    drift_count: int = 0
    pack_version: int = 0

    @property
    def display_name(self) -> str:
        # 已登入後優先顯示 MiniMax 用戶名；未登入才用別名／預設編號。
        if self.user_name:
            return self.user_name
        if self.alias:
            return self.alias
        return f"帳號 {self.id[:6]}"

    @property
    def signed_in_today(self) -> bool:
        return self.last_checkin_date == today_text()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Account":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AccountManager:
    """管理 accounts 目錄：index.json 索引 + 各帳號的 storage_state 檔。"""

    def __init__(self, encrypt: bool = True) -> None:
        self._index = paths.accounts_dir() / "index.json"
        self.encrypt = encrypt
        self._accounts: list[Account] = []
        self.load()

    # --- 索引 ---------------------------------------------------------
    def load(self) -> None:
        self._accounts = []
        if not self._index.exists():
            return
        try:
            raw = json.loads(self._index.read_text("utf-8"))
            self._accounts = [Account.from_dict(a) for a in raw.get("accounts", [])]
        except Exception:
            self._accounts = []

    def save(self) -> None:
        payload = {"accounts": [a.to_dict() for a in self._accounts]}
        tmp = self._index.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(self._index)

    # --- 查詢 ---------------------------------------------------------
    @property
    def accounts(self) -> list[Account]:
        return list(self._accounts)

    def enabled_accounts(self) -> list[Account]:
        return [a for a in self._accounts if a.enabled]

    def get(self, account_id: str) -> Account | None:
        return next((a for a in self._accounts if a.id == account_id), None)

    # --- 異動 ---------------------------------------------------------
    def add(self, alias: str = "") -> Account:
        # 防撞名：自動生成別名時跳過已存在的名稱（舊資料撞名不在此處理）。
        if not alias:
            taken = {a.alias for a in self._accounts if a.alias}
            n = len(self._accounts) + 1
            alias = f"帳號 {n}"
            while alias in taken:
                n += 1
                alias = f"帳號 {n}"
        account = Account(id=uuid.uuid4().hex, alias=alias, created_at=now_text())
        self._accounts.append(account)
        self.save()
        return account

    def remove(self, account_id: str) -> None:
        account = self.get(account_id)
        if account is None:
            return
        self.clear_state(account)
        self._accounts = [a for a in self._accounts if a.id != account_id]
        self.save()

    def update(self, account_id: str, persist: bool = True, **changes: Any) -> Account | None:
        account = self.get(account_id)
        if account is None:
            return None
        for key, value in changes.items():
            if hasattr(account, key):
                setattr(account, key, value)
        if persist:
            self.save()
        return account

    def rename(self, account_id: str, alias: str) -> tuple[bool, str]:
        """重新命名帳號別名；撞名或空白時回傳 (False, 原因）。"""
        account = self.get(account_id)
        if account is None:
            return False, "找不到帳號"
        name = (alias or "").strip()
        if not name:
            return False, "別名不可為空白"
        if len(name) > 24:
            return False, "別名太長（最多 24 字）"
        taken = {a.alias for a in self._accounts if a.id != account_id and a.alias}
        if name in taken:
            return False, f"「{name}」已被使用，請換一個名稱"
        # 若與 MiniMax 用戶名相同會造成顯示混淆，一併擋下
        others = {a.user_name for a in self._accounts if a.id != account_id and a.user_name}
        if name in others:
            return False, f"「{name}」與其他帳號的登入名稱相同，請換一個名稱"
        account.alias = name
        self.save()
        return True, ""

    def move(self, account_id: str, offset: int) -> None:
        ids = [a.id for a in self._accounts]
        if account_id not in ids:
            return
        index = ids.index(account_id)
        target = max(0, min(len(ids) - 1, index + offset))
        if target == index:
            return
        self._accounts.insert(target, self._accounts.pop(index))
        self.save()

    # --- session（storage_state） ------------------------------------
    def _state_path(self, account: Account, encrypted: bool) -> Any:
        return paths.accounts_dir() / f"{account.id}.{'bin' if encrypted else 'json'}"

    def has_state(self, account: Account) -> bool:
        return self.state_bytes(account) > 0

    def save_state(self, account: Account, state: dict[str, Any], encrypt: bool | None = None) -> None:
        encrypt = self.encrypt if encrypt is None else encrypt
        self.clear_state(account)
        blob, encrypted = crypto.dumps_state(state, encrypt=encrypt)
        self._state_path(account, encrypted).write_bytes(blob)
        account.last_login_at = now_text()
        self.update(
            account.id,
            user_name=account.user_name,
            user_id=account.user_id,
            avatar=account.avatar,
            last_login_at=account.last_login_at,
        )

    def load_state(self, account: Account) -> dict[str, Any] | None:
        bin_path = paths.accounts_dir() / f"{account.id}.bin"
        json_path = paths.accounts_dir() / f"{account.id}.json"
        try:
            if bin_path.exists():
                return crypto.loads_state(bin_path.read_bytes(), encrypted=True)
            if json_path.exists():
                return crypto.loads_state(json_path.read_bytes(), encrypted=False)
        except Exception:
            return None
        return None

    def clear_state(self, account: Account) -> None:
        for ext in ("bin", "json"):
            path = paths.accounts_dir() / f"{account.id}.{ext}"
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass

    def state_bytes(self, account: Account) -> int:
        for ext in ("bin", "json"):
            path = paths.accounts_dir() / f"{account.id}.{ext}"
            if path.exists():
                return path.stat().st_size
        return 0

    def summary(self) -> dict[str, Any]:
        today = today_text()
        enabled = self.enabled_accounts()
        done = [a for a in enabled if a.last_checkin_date == today and a.last_status in ("success", "already")]
        return {
            "total": len(self._accounts),
            "enabled": len(enabled),
            "done_today": len(done),
            "points_today": sum(a.last_points for a in done),
            "points_total": sum(a.total_points for a in self._accounts),
        }
