"""列出 Inno Setup 可攜安裝路徑與可用語言（建置輔助）。"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

PREFERRED_INNO_DIRS = (
    Path(os.environ.get("INNO_SETUP_DIR", "")) if os.environ.get("INNO_SETUP_DIR") else None,
    # 由 build_tools/bootstrap_inno.py 自動下載的可攜版本
    Path(os.environ.get("LOCALAPPDATA", "")) / "MinimaxCheckin-build" / "inno"
    if os.environ.get("LOCALAPPDATA")
    else None,
    Path(r"C:\Program Files (x86)\Inno Setup 7"),
    Path(r"C:\Program Files\Inno Setup 7"),
    Path(r"C:\Program Files (x86)\Inno Setup 6"),
    Path(r"C:\Program Files\Inno Setup 6"),
    Path(os.environ.get("TEMP", "")) / "mm_setup" / "Inno6",
)


def find_iscc() -> Path | None:
    """找出 Inno Setup 編譯器 ISCC.exe。"""
    for directory in PREFERRED_INNO_DIRS:
        if not directory:
            continue
        candidate = directory / "ISCC.exe"
        if candidate.exists():
            return candidate
    found = shutil.which("ISCC") or shutil.which("iscc")
    return Path(found) if found else None


def main() -> int:
    parser = argparse.ArgumentParser(description="檢查打包環境")
    parser.parse_args()
    iscc = find_iscc()
    print(f"Inno Setup ISCC.exe：{iscc if iscc else '找不到'}")
    if iscc:
        languages = iscc.parent / "Languages"
        if languages.is_dir():
            names = sorted(p.name for p in languages.glob("*.isl"))
            print(f"   內建語言檔 {len(names)} 個：{', '.join(names[:8])}{' …' if len(names) > 8 else ''}")
    return 0 if iscc else 1


if __name__ == "__main__":
    raise SystemExit(main())