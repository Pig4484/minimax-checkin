"""簽到介面的選擇器引擎：多候選選擇器 + 文字啟發式 + 結構指紋（抗改版）。"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from app.constants import (
    CLAIM_BUTTON_CANDIDATES,
    CLAIMED_TEXT_PATTERN,
    CLAIM_TEXT_PATTERN,
    SIGNIN_CARD,
    DayStatus,
)

_CLAIM_TEXT_RE = re.compile(CLAIM_TEXT_PATTERN, re.I)
_CLAIMED_TEXT_RE = re.compile(CLAIMED_TEXT_PATTERN, re.I)


@dataclass
class ButtonMatch:
    """命中的簽到按鈕。"""

    selector: str
    kind: str
    text: str = ""
    aria: str = ""
    disabled: bool = False
    candidates: int = 1
    locator: Any = None  # Playwright Locator（不序列化，供點擊用）

    @property
    def label(self) -> str:
        return self.aria or self.text

    @property
    def looks_claimed(self) -> bool:
        return self.disabled or bool(_CLAIMED_TEXT_RE.search(f"{self.aria} {self.text}"))


async def panel_present(page) -> bool:
    try:
        return await page.locator(SIGNIN_CARD).count() > 0
    except Exception:
        return False


async def _describe(locator) -> tuple[str, str, bool] | None:
    try:
        if not await locator.is_visible():
            return None
        text = (await locator.inner_text() or "").strip()
        aria = (await locator.get_attribute("aria-label") or "").strip()
        disabled = await locator.is_disabled()
    except Exception:
        return None
    return text, aria, disabled


async def find_claim_button(page) -> ButtonMatch | None:
    """依序嘗試候選選擇器與文字啟發式，回傳第一個可見的簽到按鈕。"""
    for selector in CLAIM_BUTTON_CANDIDATES:
        try:
            locator = page.locator(selector)
            count = await locator.count()
        except Exception:
            continue
        for index in range(count):
            info = await _describe(locator.nth(index))
            if info is None:
                continue
            text, aria, disabled = info
            kind = "class" if "signin-claim-button" in selector else "testid"
            return ButtonMatch(selector, kind, text, aria, disabled, count, locator.nth(index))

    if await panel_present(page):
        try:
            buttons = page.locator(f'{SIGNIN_CARD} button, {SIGNIN_CARD} [role="button"]')
            count = await buttons.count()
        except Exception:
            count = 0
        for index in range(count):
            locator = buttons.nth(index)
            info = await _describe(locator)
            if info is None:
                continue
            text, aria, disabled = info
            joined = f"{text} {aria}"
            if _CLAIMED_TEXT_RE.search(joined):
                continue
            if "close" in aria.lower() or "about" in aria.lower():
                continue
            if _CLAIM_TEXT_RE.search(joined):
                return ButtonMatch(
                    f"{SIGNIN_CARD} button[text-match]",
                    "text",
                    text,
                    aria,
                    disabled,
                    count,
                    locator,
                )

    try:
        buttons = page.locator("button, [role=button]")
        count = await buttons.count()
    except Exception:
        count = 0
    for index in range(min(count, 400)):
        locator = buttons.nth(index)
        info = await _describe(locator)
        if info is None:
            continue
        text, aria, disabled = info
        joined = f"{text} {aria}"
        if _CLAIMED_TEXT_RE.search(joined):
            continue
        if _CLAIM_TEXT_RE.search(joined):
            return ButtonMatch("button[text-match]", "heuristic", text, aria, disabled, count, locator)
    return None


async def button_state(page) -> str:
    """回傳 'available' / 'claimed' / 'missing'。"""
    match = await find_claim_button(page)
    if match is None:
        return "missing"
    return "claimed" if match.looks_claimed else "available"


def today_entry(status_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """從 signin/status 回應取出「今天」那一格。"""
    if not isinstance(status_payload, dict):
        return None
    data = status_payload.get("data") or {}
    for day in data.get("days") or []:
        if isinstance(day, dict) and day.get("is_today"):
            return day
    return None


def status_code_of(payload: dict[str, Any] | None) -> int | None:
    if not isinstance(payload, dict):
        return None
    code = (payload.get("base_resp") or {}).get("status_code")
    return code if isinstance(code, int) else None


def message_of(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return ""
    return str((payload.get("base_resp") or {}).get("status_msg") or "")


async def panel_days(page) -> list[dict[str, Any]]:
    """讀取面板上 7 天的視覺狀態（診斷用）。"""
    result: list[dict[str, Any]] = []
    for day_no in range(1, 8):
        try:
            locator = page.locator(f'[data-testid="signin-day-{day_no}"]')
            if await locator.count() == 0:
                continue
            cls = (await locator.get_attribute("class")) or ""
            result.append(
                {
                    "day_no": day_no,
                    "class": cls,
                    "today": "accent" in cls,
                    "text": (await locator.inner_text() or "").strip(),
                }
            )
        except Exception:
            continue
    return result


async def structural_fingerprint(page) -> str:
    """簽到相關元素的 tag+class+testid 指紋，用於偵測官方改版。"""
    try:
        raw = await page.evaluate(
            """() => {
                const nodes = [...document.querySelectorAll('[class*="signin"],[data-testid*="signin"]')];
                return nodes.map(n => n.tagName + '|' + (n.getAttribute('class') || '')
                    + '|' + (n.getAttribute('data-testid') || '')).sort().join('\\n');
            }"""
        )
    except Exception:
        return ""
    if not raw:
        return ""
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


async def heuristic_scan(page) -> dict[str, Any]:
    """掃描頁面上所有可疑元素（給 tools/probe.py 與診斷檔用）。"""
    candidates: list[dict[str, Any]] = []
    try:
        total = await page.locator("button, [role=button], a[href]").count()
    except Exception:
        total = 0
    for index in range(min(total, 500)):
        locator = page.locator("button, [role=button], a[href]").nth(index)
        info = await _describe(locator)
        if info is None:
            continue
        text, aria, disabled = info
        joined = f"{text} {aria}"
        if not (_CLAIM_TEXT_RE.search(joined) or _CLAIMED_TEXT_RE.search(joined)):
            continue
        try:
            cls = (await locator.get_attribute("class")) or ""
            testid = (await locator.get_attribute("data-testid")) or ""
        except Exception:
            cls = testid = ""
        candidates.append(
            {
                "text": text[:60],
                "aria": aria[:60],
                "disabled": disabled,
                "class": cls[:200],
                "testid": testid,
            }
        )
    return {
        "panel_present": await panel_present(page),
        "fingerprint": await structural_fingerprint(page),
        "days": await panel_days(page),
        "claim_candidates": candidates,
    }


def day_status_text(status: int | None) -> str:
    if status is None:
        return "未知"
    try:
        return {
            DayStatus.LOCKED: "未解鎖",
            DayStatus.AVAILABLE: "可簽到",
            DayStatus.CLAIMED: "已領取",
        }.get(DayStatus(status), f"未知({status})")
    except ValueError:
        return f"未知({status})"
