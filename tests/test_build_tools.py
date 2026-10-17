"""建置工具測試（免安裝版說明檔、版本同步）。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build_tools"))


def test_version_matches_constants():
    """打包版本必須與 app/constants.py 的 APP_VERSION 同步。"""
    from app.constants import APP_VERSION

    import build as build_module

    assert build_module.read_version() == APP_VERSION


def test_portable_readme_contents():
    import build as build_module

    text = build_module.portable_readme_text("1.2.3", "full")

    assert "1.2.3" in text
    assert "免安裝版" in text
    # 免安裝版預設即為完全可攜：資料寫 exe 旁 data，不寫 AppData。
    assert ".\\data\\config.json" in text, "必須說明預設寫入 exe 旁 data"
    assert "portable.flag" in text, "必須說明完全可攜模式"
    assert "傳送到桌面當捷徑" in text, "必須教使用者用捷徑而非搬 exe 本體"
    assert "已內建 Chromium" in text


def test_portable_readme_lite_flavor():
    import build as build_module

    text = build_module.portable_readme_text("1.0.0", "lite")
    assert "未內建 Chromium" in text
    assert "Chrome" in text and "Edge" in text


def test_build_tools_can_print_unicode_without_crashing(tmp_path, monkeypatch, capsys):
    """Windows 繁中環境預設編碼 cp950 無法輸出 emoji，
    建置工具必須先切換成 UTF-8，否則列印進度時會以 UnicodeEncodeError 中斷建置。
    """
    import io

    import bootstrap_inno
    import build as build_module

    for module in (build_module, bootstrap_inno):
        assert hasattr(module, "enable_utf8_console"), f"{module.__name__} 缺少 UTF-8 修正"
        # 模擬 cp950 的輸出串流：能寫入中文但寫入 emoji 會失敗
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp950", errors="strict")
        monkeypatch.setattr(sys, "stdout", stream)
        monkeypatch.setattr(sys, "stderr", stream)
        module.enable_utf8_console()
        print("完成 ✅ 建置")  # 修正後不應拋出例外


def test_portable_zip_layout(tmp_path, monkeypatch):
    """ZIP 內應有單一頂層資料夾、含說明檔，且不含任何 .lnk 捷徑。"""
    import build as build_module
    import zipfile

    app_dir = tmp_path / "app"
    (app_dir / "_internal").mkdir(parents=True)
    (app_dir / "MinimaxCheckin.exe").write_bytes(b"MZ")
    (app_dir / "_internal" / "data.bin").write_bytes(b"x")
    (app_dir / "should_not_exist.lnk").write_bytes(b"")  # 不該被帶進 ZIP

    monkeypatch.setattr(build_module, "DIST", tmp_path / "dist")
    archive = build_module.create_portable_zip(app_dir, "9.9.9", "full")

    assert archive.exists()
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()

    top_level = {name.split("/")[0] for name in names}
    assert top_level == {"MiniMax Check-in"}, f"需為單一頂層資料夾，實際：{top_level}"
    assert "MiniMax Check-in/MinimaxCheckin.exe" in names
    assert "MiniMax Check-in/_internal/data.bin" in names
    assert "MiniMax Check-in/免安裝版說明.txt" in names
    assert "MiniMax Check-in/portable.flag" in names, "免安裝版必須預帶 portable.flag（解壓即隔離）"
    assert not any(name.lower().endswith(".lnk") for name in names), "免安裝版不得含桌面捷徑"
    # 說明檔只能存在於 ZIP 內，不得落地到執行檔目錄（否則安裝版也會帶上它）
    assert not (app_dir / "免安裝版說明.txt").exists(), "說明檔不應寫入執行檔目錄"