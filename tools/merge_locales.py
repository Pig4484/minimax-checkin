"""把 zh-TW 新增的 key 合併到 zh-CN / en（值先用繁中佔位，再手動翻譯）。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "app" / "locales"
tw = json.loads((ROOT / "zh-TW.json").read_text("utf-8"))
for name in ("zh-CN", "en"):
    path = ROOT / f"{name}.json"
    other = json.loads(path.read_text("utf-8"))
    added = 0
    for key, value in tw.items():
        if key not in other:
            other[key] = value
            added += 1
    path.write_text(json.dumps(other, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(name, "added:", added, "total:", len(other))
