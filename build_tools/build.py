"""一鍵建置：PyInstaller 打包 → Inno Setup 產生安裝程式。

用法（於專案根目錄執行）::

    .venv\\Scripts\\python.exe build_tools\\build.py                 # 完整版（含內建 Chromium）
    .venv\\Scripts\\python.exe build_tools\\build.py --flavor lite   # 精簡版（不含瀏覽器核心）
    .venv\\Scripts\\python.exe build_tools\\build.py --no-installer  # 只產生執行檔目錄

輸出::

    dist\\MinimaxCheckin\\                     執行檔目錄（可直接執行）
    dist\\installer\\MiniMaxCheckin-Setup-<版本>-<flavor>.exe
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
PACKAGING = PROJECT / "build_tools"
DIST = PROJECT / "dist"
BUILD = PROJECT / "build"

sys.path.insert(0, str(PACKAGING))
from find_iscc import find_iscc  # noqa: E402

APP_NAME = "MiniMax Check-in"


def enable_utf8_console() -> None:
    """強制輸出使用 UTF-8（Windows 繁中環境預設 cp950 無法輸出 emoji，會讓建置中斷）。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def read_version() -> str:
    text = (PROJECT / "app" / "constants.py").read_text("utf-8")
    match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else "0.0.0"


def expected_chromium_revision() -> str | None:
    """讀取 Playwright 內建的 browsers.json，取得它實際使用的 Chromium 版本。"""
    try:
        import json

        import playwright

        registry = Path(playwright.__file__).parent / "driver" / "package" / "browsers.json"
        data = json.loads(registry.read_text("utf-8"))
        for entry in data.get("browsers", []):
            if entry.get("name") == "chromium":
                return str(entry.get("revision"))
    except Exception:
        return None
    return None


def find_browsers_dir() -> tuple[Path | None, str | None]:
    """找出含「Playwright 實際需要版本」Chromium 的目錄。"""
    revision = expected_chromium_revision()
    candidates = []
    if os.environ.get("MM_PLAYWRIGHT_DIR"):
        candidates.append(Path(os.environ["MM_PLAYWRIGHT_DIR"]))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "ms-playwright")
    for directory in candidates:
        if not directory.is_dir():
            continue
        wanted = f"chromium-{revision}" if revision else None
        if wanted and (directory / wanted).is_dir():
            return directory, wanted
        # 找不到精確版本時，退回最新的完整 Chromium
        chromium = sorted(
            (
                item
                for item in directory.iterdir()
                if item.is_dir()
                and item.name.startswith("chromium-")
                and not item.name.startswith("chromium_headless")
            ),
            key=lambda p: p.name,
        )
        if chromium:
            return directory, chromium[-1].name
    return None, None


def chromium_size(browsers_dir: Path, folder_name: str) -> int:
    total = 0
    target = browsers_dir / folder_name
    if not target.is_dir():
        return 0
    for file in target.rglob("*"):
        if file.is_file():
            try:
                total += file.stat().st_size
            except OSError:
                pass
    return total


def write_version_info(version: str) -> Path:
    """產生 PyInstaller 版本資源（與 app/constants.py 保持同步）。"""
    parts = [int(p) if p.isdigit() else 0 for p in version.split(".")]
    while len(parts) < 4:
        parts.append(0)
    tuple_version = ", ".join(str(p) for p in parts[:4])
    path = PACKAGING / "_version_info.txt"
    path.write_text(
        f"""# 由 packaging/build.py 自動產生，請勿手動編輯
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({tuple_version}), prodvers=({tuple_version}),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', '{APP_NAME} Project'),
        StringStruct('FileDescription', 'MiniMax Agent 自動簽到工具'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', 'MinimaxCheckin'),
        StringStruct('LegalCopyright', 'Licensed under GNU GPL v3'),
        StringStruct('OriginalFilename', 'MinimaxCheckin.exe'),
        StringStruct('ProductName', '{APP_NAME}'),
        StringStruct('ProductVersion', '{version}')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""",
        "utf-8",
    )
    return path


def run(command: list[str], env: dict[str, str] | None = None) -> int:
    print(f"\n$ {' '.join(command)}", flush=True)
    started = time.monotonic()
    process = subprocess.run(command, cwd=str(PROJECT), env=env)
    print(f"  → 結束碼 {process.returncode}（{time.monotonic() - started:.1f}s）", flush=True)
    return process.returncode


def directory_size(path: Path) -> int:
    total = 0
    for file in path.rglob("*"):
        if file.is_file():
            try:
                total += file.stat().st_size
            except OSError:
                pass
    return total


def mb(size: int) -> str:
    return f"{size / (1024 * 1024):.1f} MB"


PORTABLE_README = """\
================================================================================
 {app_name} {version} — 免安裝版（Portable）
================================================================================

【這是什麼】
本版本不需要安裝程式，解壓縮後直接執行即可，可放在 USB 隨身碟使用。
與安裝版功能完全相同（同樣支援開機自啓動、系統匣常駐、每日自動簽到）。

【使用方式】
1. 將整個資料夾解壓縮到任何位置（建議 D:\\Apps\\{folder} 等程式專用資料夾）
2. 雙擊 MinimaxCheckin.exe 即可啟動
3. 首次使用請到「帳號」頁按「新增帳號」完成一次登入（之後不必再登入）

【重要：請勿解壓縮到桌面】
依 Windows 使用慣例，本程式不會在桌面建立或存放任何檔案。請將本資料夾放在
程式專用目錄（例如 D:\\Apps\\{folder}），保持桌面整潔。

【資料存放位置（與安裝版相同）】
  設定檔：%APPDATA%\\MinimaxCheckin\\config.json
  本機資料：%LOCALAPPDATA%\\MinimaxCheckin\\
            （帳號登入狀態 accounts\\、日誌 logs\\、診斷 diagnostics\\）
  * 這是 Windows 應用程式的標準位置：設定隨使用者漫遊，加密的登入狀態留在本機
  * 不會寫入桌面、不會寫入 Program Files

【完全可攜模式（進階，選用）】
若希望所有資料都存放在本資料夾內（例如放在 USB 隨身碟帶著走），
請在本資料夾內新增一個空檔案並命名為：portable.flag
之後所有資料會改存到 data\\ 子資料夾，完全不寫入 AppData。

【移除方式】
刪除整個資料夾即可。若先前使用過「開機自啓動」，請先開啟程式於
「設定」頁關閉該選項，或手動移除登錄檔項目：
  HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\\MinimaxCheckin

【瀏覽器核心】
{browser_note}

【授權】
GNU General Public License v3.0（詳見 LICENSE）
第三方元件清單請見 THIRD-PARTY-NOTICES.md
本程式為非官方第三方工具，與 MiniMax 無隸屬關係。
================================================================================
"""


def portable_readme_text(version: str, flavor: str) -> str:
    """免安裝版說明檔內容。"""
    if flavor == "full":
        browser_note = "本版本已內建 Chromium，無需額外下載。"
    else:
        browser_note = (
            "本版本未內建 Chromium：首次使用會自動改用系統的 "
            "Google Chrome 或 Microsoft Edge；也可在程式「設定 → 瀏覽器核心狀態」"
            "按「下載核心」（約 150MB）。"
        )
    return PORTABLE_README.format(
        app_name=APP_NAME,
        version=version,
        folder="MiniMax Check-in",
        browser_note=browser_note,
    )


def create_portable_zip(app_dir: Path, version: str, flavor: str) -> Path:
    """把執行檔目錄打包成免安裝版 ZIP（解壓即用）。

    注意：
    * ZIP 內**不含**任何 .lnk 捷徑，不會在使用者桌面產生檔案
    * 說明檔只寫入 ZIP 內，不會留在執行檔目錄（避免安裝版也帶上免安裝說明）
    """
    import zipfile

    output_dir = DIST / "portable"
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"MiniMaxCheckin-Portable-{version}-{flavor}.zip"

    # 排除捷徑與暫存檔；免安裝版不得夾帶任何 .lnk
    skip_suffixes = {".lnk", ".url", ".tmp", ".log"}
    files = [
        path
        for path in sorted(app_dir.rglob("*"))
        if path.is_file() and path.suffix.lower() not in skip_suffixes
    ]
    total_bytes = sum(p.stat().st_size for p in files)
    prefix = Path("MiniMax Check-in")
    print(f"      壓縮 {len(files) + 1} 個項目（{mb(total_bytes)}）→ {archive.name}")

    started = time.monotonic()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        # 說明檔直接寫進 ZIP，不落地到執行檔目錄
        zf.writestr(
            str(prefix / "免安裝版說明.txt"),
            portable_readme_text(version, flavor).encode("utf-8"),
        )
        for index, path in enumerate(files, 1):
            zf.write(path, prefix / path.relative_to(app_dir))
            if index % 100 == 0:
                print(f"        …{index}/{len(files)}", flush=True)
    print(f"      完成（{time.monotonic() - started:.1f}s）")
    return archive


def main() -> int:
    enable_utf8_console()
    parser = argparse.ArgumentParser(description=f"{APP_NAME} 建置工具")
    parser.add_argument(
        "--flavor",
        choices=("full", "lite"),
        default="full",
        help="full：內建 Chromium；lite：不含瀏覽器核心",
    )
    parser.add_argument("--no-installer", action="store_true", help="只產生執行檔，不產生安裝程式")
    parser.add_argument("--no-portable", action="store_true", help="不產生免安裝版 ZIP")
    parser.add_argument("--keep-build", action="store_true", help="保留 PyInstaller 中間檔（build/）")
    args = parser.parse_args()

    version = read_version()
    print("=" * 70)
    print(f" {APP_NAME} 建置程式")
    print(f" 版本：{version}｜模式：{args.flavor}")
    print("=" * 70)

    # --- 1. 準備版本資源與瀏覽器 ----------------------------------------
    version_file = write_version_info(version)
    print(f"[1/3] 版本資源：{version_file.name}")

    env = os.environ.copy()
    browsers_dir, chromium_folder = find_browsers_dir()
    if args.flavor == "full":
        if browsers_dir and chromium_folder:
            env["MM_BUNDLE_BROWSERS"] = "1"
            env["MM_PLAYWRIGHT_DIR"] = str(browsers_dir)
            env["MM_CHROMIUM_FOLDER"] = chromium_folder
            size = chromium_size(browsers_dir, chromium_folder)
            print(f"      內建瀏覽器：{browsers_dir / chromium_folder}（{mb(size)}）")
        else:
            print("      ⚠ 找不到 Chromium，將改以精簡版打包（首次執行可下載或用系統 Chrome/Edge）")
            env["MM_BUNDLE_BROWSERS"] = "0"
    else:
        env["MM_BUNDLE_BROWSERS"] = "0"
        print("      精簡版：不內建瀏覽器核心")
    env["MM_VERSION_INFO"] = str(version_file)

    # --- 2. PyInstaller ---------------------------------------------------
    print("\n[2/3] PyInstaller 打包中（視內建瀏覽器大小，可能需要數分鐘）…")
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        str(PACKAGING / "MinimaxCheckin.spec"),
        "--distpath",
        str(DIST),
        "--workpath",
        str(BUILD),
    ]
    if not args.keep_build:
        command.append("--clean")
    if run(command, env=env) != 0:
        print("❌ PyInstaller 失敗")
        return 1

    app_dir = DIST / "MinimaxCheckin"
    exe_path = app_dir / "MinimaxCheckin.exe"
    if not exe_path.exists():
        print(f"❌ 找不到輸出檔：{exe_path}")
        return 1
    print(f"      執行檔：{exe_path}（目錄 {mb(directory_size(app_dir))}）")

    # --- 3. 免安裝版 ZIP --------------------------------------------------
    portable_zip: Path | None = None
    if not args.no_portable:
        print("\n[3/4] 產生免安裝版（Portable）ZIP…")
        try:
            portable_zip = create_portable_zip(app_dir, version, args.flavor)
        except Exception as exc:
            print(f"      ⚠ 免安裝版打包失敗：{exc}")
            portable_zip = None

    if args.no_installer:
        print("\n" + "=" * 70)
        print("完成（略過安裝程式）")
        print(f"   執行檔目錄：{app_dir}")
        if portable_zip:
            print(f"   免安裝版：{portable_zip}（{mb(portable_zip.stat().st_size)}）")
        print("=" * 70)
        return 0

    # --- 4. Inno Setup ----------------------------------------------------
    iscc = find_iscc()
    if iscc is None:
        print("\n[4/4] 找不到 Inno Setup，嘗試自動取得可攜版本…")
        try:
            from bootstrap_inno import download

            iscc = download()
        except Exception as exc:
            print(f"   自動取得失敗：{exc}")
            iscc = None
    if iscc is None:
        print("\n❌ 找不到 Inno Setup 的 ISCC.exe")
        print("   請執行 build_tools\\bootstrap_inno.py，或手動安裝 Inno Setup 6/7，")
        print("   或設定環境變數 INNO_SETUP_DIR 指向安裝目錄。")
        print(f"   目前仍可使用的輸出：{app_dir}")
        if portable_zip:
            print(f"   免安裝版：{portable_zip}")
        return 1

    print(f"\n[4/4] Inno Setup 產生安裝程式（{iscc}）…")
    code = run(
        [
            str(iscc),
            f"/DAppVersion={version}",
            f"/DFlavor={args.flavor}",
            str(PACKAGING / "installer.iss"),
        ]
    )
    if code != 0:
        print("❌ Inno Setup 失敗")
        return 1

    installer = DIST / "installer" / f"MiniMaxCheckin-Setup-{version}-{args.flavor}.exe"
    print("\n" + "=" * 70)
    print("建置完成！")
    print("=" * 70)
    if installer.exists():
        print(f"📦 安裝包：{installer}")
        print(f"   {mb(installer.stat().st_size)}")
    else:
        print("⚠ 找不到預期的安裝程式輸出，請檢查 dist\\installer 目錄")

    if portable_zip is not None and portable_zip.exists():
        print(f"🗂  免安裝版：{portable_zip}")
        print(f"   {mb(portable_zip.stat().st_size)}（解壓即用，不需安裝）")

    print(f"📁 執行檔目錄：{app_dir}（{mb(directory_size(app_dir))}）")
    print()
    print("提醒：兩個版本都不會在桌面產生任何檔案（桌面捷徑僅由安裝精靈的")
    print("      「建立桌面捷徑（選用）」選項建立，且預設不勾選）。")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())