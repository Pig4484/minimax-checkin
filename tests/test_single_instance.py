"""單一實例喚醒測試（獨立子行程執行，避免 QLocalServer 污染其他 Qt 測試）。

背景：QLocalServer 在 Windows 用 session 內命名管道，同一 pytest 行程內
若有殘留 server，會干擾 test_theme 等其他 Qt 測試。因此本檔只做「收集器」，
真正的喚醒往返在子行程（test helper）中執行，父行程只斷言結束碼。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HELPER = Path(__file__).parent / "helpers" / "single_instance_probe.py"


def _run_probe(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HELPER), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_wake_existing_reaches_server():
    proc = _run_probe("roundtrip")
    assert proc.returncode == 0, f"喚醒往返失敗：{proc.stdout}\n{proc.stderr}"
    assert "ROUNDTRIP-OK" in proc.stdout


def test_wake_existing_without_server_returns_false():
    proc = _run_probe("no-server")
    assert proc.returncode == 0, f"無 server 應回 False：{proc.stdout}\n{proc.stderr}"
    assert "NO-SERVER-OK" in proc.stdout


def test_acquire_single_instance_semantics_preserved():
    import main as entry

    assert callable(entry.acquire_single_instance)
    from app.single_instance import wake_existing as impl

    assert entry.wake_existing is impl


def test_main_does_not_reference_instance_before_assignment():
    """迴歸：holder['instance'] 必須在 acquire 之後賦值，否則每次啟動 NameError 秒退。

    背景：曾把 holder['instance'] = instance 寫在 instance 賦值之前，
    pythonw 下無主控台、NameError 靜默死亡，表現為「秒退、沒 GUI、沒對話框」。
    """
    import ast
    from pathlib import Path

    tree = ast.parse((Path(__file__).parent.parent / "main.py").read_text("utf-8"))
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "main")
    order: list[tuple[str, int]] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Assign):
            targets = "".join(ast.dump(t) for t in node.targets)
            if "holder" in targets and "instance" in targets:
                order.append(("holder_store", node.lineno))
            if any(isinstance(t, ast.Name) and t.id == "instance" for t in node.targets):
                order.append(("instance_assign", node.lineno))
    stores = [ln for kind, ln in order if kind == "holder_store"]
    assigns = [ln for kind, ln in order if kind == "instance_assign"]
    assert assigns, "main() 應有 instance = acquire_single_instance() 賦值"
    assert stores, "main() 應把 Mutex handle 留在 holder"
    assert min(assigns) < min(stores), "holder['instance'] 不可在 instance 賦值之前寫入"
