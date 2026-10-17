"""以 GitHub REST API 建立 v1.0.1 Release 並上傳打包附件。

用法（PowerShell）：
    $env:GITHUB_TOKEN = "<PAT>"
    .\.venv\Scripts\python.exe tools/make_release.py

讀取 docs/release-v1.0.1.md 當 release 內文，上傳 dist/ 下兩個 full 產物。
只用標準庫（urllib），無需額外依賴。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request

OWNER = "Pig4484"
REPO = "minimax-checkin"
TAG = "v1.0.1"
NAME = "v1.0.1"
DRAFT = False
PRERELEASE = False
NOTES_PATH = os.path.join("docs", "release-v1.0.1.md")
ASSETS = [
    os.path.join("dist", "installer", "MiniMaxCheckin-Setup-1.0.1-full.exe"),
    os.path.join("dist", "portable", "MiniMaxCheckin-Portable-1.0.1-full.zip"),
]
API = "https://api.github.com"


def _req(url: str, token: str, data: bytes | None = None,
         method: str = "GET", ctype: str = "application/json",
         timeout: float | None = 30) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "minimax-checkin-release-script")
    if data is not None:
        req.add_header("Content-Type", ctype)
        req.add_header("Content-Length", str(len(data)))
    try:
        # 大附件上傳：timeout=None 讓 socket 在有持續寫入時不被斷線；
        # VPN 下慢速上傳也適用（僅連線建立階段受 connect timeout 保護）。
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:  # type: ignore[attr-defined]
        return exc.code, exc.read()


def _upload_with_retry(url: str, token: str, data: bytes, name: str,
                       tries: int = 3) -> tuple[int, bytes]:
    last: tuple[int, bytes] = (0, b"")
    for attempt in range(1, tries + 1):
        print(f"ATTEMPT {attempt}/{tries} {name} ...", flush=True)
        try:
            last = _req(url, token, data=data, method="POST",
                        ctype="application/octet-stream", timeout=None)
        except Exception as exc:  # 超時/斷線：等 10 秒再試
            print(f"RETRYABLE {name}: {type(exc).__name__}: {exc}", flush=True)
            import time
            time.sleep(10)
            continue
        status = last[0]
        if status in (200, 201):
            return last
        print(f"RETRYABLE {name}: HTTP {status}: {last[1][:200]!r}", flush=True)
        import time
        time.sleep(10)
    return last


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("ERROR: GITHUB_TOKEN is empty", flush=True)
        return 1
    for path in [NOTES_PATH, *ASSETS]:
        if not os.path.isfile(path):
            print(f"ERROR: missing file: {path}", flush=True)
            return 1
    with open(NOTES_PATH, encoding="utf-8") as fh:
        body = fh.read()

    # 1) 若同 tag 的 release 已存在，直接重用（避免重複建）。
    status, raw = _req(f"{API}/repos/{OWNER}/{REPO}/releases/tags/{TAG}", token)
    if status == 200:
        rel = json.loads(raw.decode("utf-8"))
        print(f"REUSE release id={rel['id']} url={rel.get('html_url')}", flush=True)
    elif status == 404:
        payload = json.dumps({
            "tag_name": TAG, "name": NAME, "body": body,
            "draft": DRAFT, "prerelease": PRERELEASE,
        }).encode("utf-8")
        status, raw = _req(f"{API}/repos/{OWNER}/{REPO}/releases", token,
                           data=payload, method="POST")
        if status not in (200, 201):
            print(f"ERROR: create release -> {status}: {raw[:500]!r}", flush=True)
            return 1
        rel = json.loads(raw.decode("utf-8"))
        print(f"CREATED release id={rel['id']} url={rel.get('html_url')}", flush=True)
    else:
        print(f"ERROR: get release -> {status}: {raw[:500]!r}", flush=True)
        return 1

    upload_url = rel["upload_url"].split("{")[0]
    existing = {a["name"]: a["id"] for a in rel.get("assets", [])}

    for path in ASSETS:
        name = os.path.basename(path)
        if name in existing:
            print(f"SKIP {name} (already attached)", flush=True)
            continue
        size = os.path.getsize(path)
        print(f"UPLOAD {name} ({size / 1048576:.1f} MB) ...", flush=True)
        with open(path, "rb") as fh:
            data = fh.read()
        url = f"{upload_url}?{urllib.parse.urlencode({'name': name})}"
        status, raw = _upload_with_retry(url, token, data, name)
        if status not in (200, 201):
            print(f"ERROR: upload {name} -> {status}: {raw[:500]!r}", flush=True)
            return 1
        print(f"UPLOADED {name}", flush=True)

    print(f"DONE {rel.get('html_url')}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
