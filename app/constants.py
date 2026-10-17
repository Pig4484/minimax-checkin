"""全域常數：應用資訊、目標站台、選擇器包版本、狀態列舉。"""

from __future__ import annotations

from enum import IntEnum
from enum import Enum

APP_NAME = "Minimax Check-in"
APP_NAME_CN = "MiniMax 自動簽到"
APP_VERSION = "1.0.1"
APP_ID = "MinimaxCheckin"
ORG_NAME = "MinimaxCheckin"
PROJECT_URL = "https://github.com/"

# --- 目標站台 ---------------------------------------------------------------
BASE_URL = "https://agent.minimax.io/"
LOGIN_HOST = "account.minimax.io"
CALLBACK_PATH = "/auth/callback"

# 由真實 Chrome 取得，避免 headless 的 "HeadlessChrome" 特徵
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
)

# --- API 路徑片段（用於網路回應攔截） --------------------------------------
API_SIGNIN_STATUS = "/minimax-cloud/api/v1/signin/status"
API_SIGNIN_CLAIM = "/minimax-cloud/api/v1/signin/claim"
API_SIGNIN_CONFIG = "/minimax-cloud/api/v1/signin/config"
API_USER_INFO = "/v1/api/user/info"

# --- 選擇器包 ---------------------------------------------------------------
# 官方頁面改版時遞增此版本，並更新 selectors.py / tests/fixtures
SELECTOR_PACK_VERSION = 1

SIGNIN_CARD = '[data-testid="signin-card"]'
SIGNIN_DAY = '[data-testid="signin-day-%d"]'
CLAIM_BUTTON_XPATH = "xpath=//button[contains(@class,'signin-claim-button')]"
CLOSE_BUTTON = 'button[aria-label="Close check-in"]'

# 依可靠度排序的候選選擇器
CLAIM_BUTTON_CANDIDATES = (
    "button.signin-claim-button",
    '[data-testid="signin-card"] button[aria-label^="Check in for"]',
    '[data-testid="signin-card"] button[aria-label*="Check in"]',
    # 面板內排除「關閉／說明」後剩下的唯一按鈕
    '[data-testid="signin-card"] button:not([aria-label*="Close"])'
    ':not([aria-label*="About"])',
)

LOGIN_STATE_SIGNED_OUT = '[data-testid="sidebar-signed-out-login"]'
LOGIN_STATE_SIGNED_IN = '[data-testid="sidebar-user-menu-trigger"]'

# 已簽到的文字特徵（DOM 備援判定用）
CLAIMED_TEXT_PATTERN = r"checked\s*in|come\s*back\s*tomorrow|already|已簽到|明天再來"
CLAIM_TEXT_PATTERN = r"check\s*in|check-in|簽到|打卡"


class DayStatus(IntEnum):
    """`signin/status` 回應中 days[].status 的語意。"""

    LOCKED = 1       # 尚未解鎖
    AVAILABLE = 2    # 今日可簽
    CLAIMED = 3      # 已領取


class RunStatus(str, Enum):
    """單一帳號一次的執行結果。"""

    SUCCESS = "success"            # 簽到成功
    ALREADY = "already"            # 今日已簽到
    NEED_RELOGIN = "need_relogin"  # 需要重新登入
    RATE_LIMITED = "rate_limited"  # 被風控/限流
    DRIFT = "drift"                # 找不到簽到介面（疑似改版）
    FAILED = "failed"              # 其他失敗
    SKIPPED = "skipped"            # 停用/略過

    @property
    def is_ok(self) -> bool:
        return self in (RunStatus.SUCCESS, RunStatus.ALREADY)

    @property
    def retriable(self) -> bool:
        return self in (RunStatus.FAILED, RunStatus.RATE_LIMITED)


RUN_STATUS_TEXT = {
    RunStatus.SUCCESS: "runstatus.success",
    RunStatus.ALREADY: "runstatus.already",
    RunStatus.NEED_RELOGIN: "runstatus.relogin",
    RunStatus.RATE_LIMITED: "runstatus.ratelimit",
    RunStatus.DRIFT: "runstatus.drift",
    RunStatus.FAILED: "runstatus.failed",
    RunStatus.SKIPPED: "runstatus.skipped",
}


def run_status_text(status: RunStatus) -> str:
    """執行狀態顯示文字（執行時查表，跟隨目前語言）。"""
    from app.i18n import t

    key = RUN_STATUS_TEXT.get(status, "runstatus.unknown")
    return t(key)
