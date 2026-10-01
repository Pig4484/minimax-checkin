"""自動取得 Inno Setup 編譯器（可攜模式，不污染系統）。

下載並解壓到 ``%LOCALAPPDATA%\\MinimaxCheckin-build\\inno``，因此建置流程完全免手動安裝。
若系統已安裝 Inno Setup 6/7 則直接使用之。

用法::

    python build_tools\\bootstrap_inno.py           # 檢查，必要时下載
    python build_tools\\bootstrap_inno.py --force   # 強制重新下載
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from find_iscc import find_iscc  # noqa: E402


def enable_utf8_console() -> None:
    """強制輸出使用 UTF-8。

    Windows 繁體中文環境的預設編碼是 cp950，無法輸出 ✅ 等字元，
    會讓建置程序在列印訊息時以 UnicodeEncodeError 中斷。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

INNO_VERSION = "6.7.3"
DOWNLOAD_URL = (
    f"https://github.com/jrsoftware/issrc/releases/download/"
    f"is-{INNO_VERSION.replace('.', '_')}/innosetup-{INNO_VERSION}.exe"
)


def cache_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    return Path(base) / "MinimaxCheckin-build" / "inno"


def download(force: bool = False) -> Path | None:
    """下載並以可攜模式展開 Inno Setup；回傳 ISCC.exe 路徑。"""
    if not force:
        existing = find_iscc()
        if existing is not None:
            print(f"已找到 Inno Setup：{existing}")
            return existing

    target = cache_dir()
    iscc = target / "ISCC.exe"
    if iscc.exists() and not force:
        print(f"使用快取的可攜版 Inno Setup：{iscc}")
        return iscc

    target.mkdir(parents=True, exist_ok=True)
    installer = target / f"innosetup-{INNO_VERSION}.exe"
    if not installer.exists() or force:
        print(f"下載 Inno Setup {INNO_VERSION} …（約 10MB）")
        print(f"  來源：{DOWNLOAD_URL}")
        try:
            with urllib.request.urlopen(DOWNLOAD_URL, timeout=180) as response:
                data = response.read()
        except Exception as exc:
            print(f"❌ 下載失敗：{exc}")
            print("   請手動安裝 Inno Setup：https://jrsoftware.org/isdl.php")
            return None
        installer.write_bytes(data)
        print(f"  已下載 {len(data) / 1024 / 1024:.1f} MB")

    print("以可攜模式展開（不寫入系統登錄檔）…")
    command = [
        str(installer),
        "/PORTABLE=1",
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/NOICONS",
        f"/DIR={target}",
    ]
    try:
        subprocess.run(command, check=True, timeout=300)
    except Exception as exc:
        print(f"❌ 展開失敗：{exc}")
        return None

    if iscc.exists():
        print(f"✅ 就緒：{iscc}")
        return iscc
    print("❌ 找不到 ISCC.exe")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="取得 Inno Setup 編譯器")
    parser.add_argument("--force", action="store_true", help="強制重新下載")
    args = parser.parse_args()
    enable_utf8_console()
    return 0 if download(force=args.force) else 1


if __name__ == "__main__":
    raise SystemExit(main())