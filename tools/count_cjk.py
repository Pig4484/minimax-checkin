import io
import pathlib
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 日誌／註解／開發者訊息不進翻譯：只統計「可能顯示給使用者」的中文
SKIP_FILES = {
    "app/i18n.py",
    "app/logger.py",
    "app/core/diagnostics.py",
    "app/core/state.py",
    "app/core/selectors.py",
    "app/core/crypto.py",
    "app/ui/icon.py",
}
rx = re.compile(r"[\u4e00-\u9fff]")
files = list(pathlib.Path("app").rglob("*.py")) + [pathlib.Path("main.py")]
rows = []
for path in sorted(files):
    name = str(path).replace("\\", "/")
    if name in SKIP_FILES:
        continue
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [(i + 1, line.strip()[:110]) for i, line in enumerate(lines) if rx.search(line)]
    # 扣掉純註解行（# 開頭）與 docstring 行（""" 開頭）
    hits = [
        (n, text)
        for n, text in hits
        if not text.lstrip().startswith(("#", '"""', "'''"))
    ]
    if hits:
        rows.append((name, hits))
total = sum(len(h) for _, h in rows)
print("USER-FACING-CJK-LINES:", total)
for name, hits in sorted(rows, key=lambda item: -len(item[1])):
    print(f"{len(hits):>4}  {name}")
    for num, text in hits[:12]:
        print(f"      {num}: {text}")
