"""把 merge 佔位的繁中值翻成簡中／英文（審過的對照表）。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "app" / "locales"

CN_FIX = {
    "login.state.signed": "已登录",
}

EN_FIX = {
    "login.state.signed": "Signed in",
}

for name, fix in (("zh-CN", CN_FIX), ("en", EN_FIX)):
    path = ROOT / f"{name}.json"
    table = json.loads(path.read_text("utf-8"))
    table.update(fix)
    path.write_text(json.dumps(table, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(name, "fixed:", len(fix))
