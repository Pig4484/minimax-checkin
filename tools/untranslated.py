"""比對翻譯是否寫入（結果寫檔，不直接印簡中避免 cp950 炸掉）。

注意：簡繁本來就有大量同形字（取消／分鐘／版本…），
這些「值相同」不代表沒翻譯。真正的未翻譯看 tools/needs_review.txt。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "app" / "locales"
REVIEWED_SAME = {
    "accounts.card.disabled",
    "home.cancel",
    "home.status.fail",
    "home.status.idle",
    "home.status.ok",
    "logs.clear",
    "logs.level.all",
    "logs.level.info",
    "logs.level.warn",
    "notify.account.delete.cancel",
    "notify.account.rename.cancel",
    "notify.local.clear.cancel",
    "notify.local.clear.ok",
    "notify.sessions.clear.cancel",
    "notify.sessions.clear.ok",
    "settings.clear_local.all",
    "settings.clear_sessions.all",
    "settings.daily_time.cancel",
    "settings.daily_time.minute",
    "settings.daily_time.now",
    "settings.drift.suffix",
    "settings.log_days.suffix",
    "settings.notices.hint",
    "settings.proxy.hint",
    "settings.proxy.placeholder",
    "settings.retry.suffix",
    "settings.timeout.suffix",
    "settings.version",
    "status.disabled",
    "tray.still_running.ok",
    "settings.time.picked",
    "login.net.blocked",
    "login.net.dns",
    "login.net.failed",
    "login.net.network",
    "login.net.proxy",
    "login.net.ssl",
    "login.net.timeout",
    "login.net.timeout2",
    "login.net.unknown",
    # 簡繁同形字（字形相同但屬正常翻譯）：停用／可用／取消／分／ID 前綴等
    "accounts.card.off",
    "browser.launch.tried_detail",
    "checkin.cancelled",
    "settings.browser.ok",
    "settings.time.cancel",
    "settings.time.minute",
    "status.id_prefix",
}
tw = json.loads((ROOT / "zh-TW.json").read_text("utf-8"))
lines = []
for name in ("zh-CN", "en"):
    other = json.loads((ROOT / f"{name}.json").read_text("utf-8"))
    same = sorted(k for k in tw if other.get(k) == tw[k])
    if name == "zh-CN":
        need = [k for k in same if k not in REVIEWED_SAME]
    else:
        need = same
    lines.append(f"{name} untranslated: {len(need)}")
    lines.extend(f"  {k}" for k in need)
out = ROOT / "untranslated.txt"
out.write_text("\n".join(lines) + "\n", "utf-8")
print("wrote", out, "lines:", len(lines))
