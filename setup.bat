@echo off
rem === MiniMax 自動簽到：一鍵建立環境 ===
setlocal
cd /d "%~dp0"

echo ============================================
echo  MiniMax 自動簽到 - 環境安裝
echo ============================================

where uv >nul 2>nul
if %errorlevel%==0 (
    echo [1/3] 使用 uv 建立虛擬環境 .venv ...
    uv venv --python 3.11 .venv || goto :err
    echo [2/3] 安裝依賴套件 ...
    uv pip install --python ".venv\Scripts\python.exe" -r requirements.txt || goto :err
) else (
    echo [1/3] 使用內建 venv 建立虛擬環境 .venv ...
    python -m venv .venv || goto :err
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    echo [2/3] 安裝依賴套件 ...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :err
)

echo [3/3] 下載 Playwright Chromium（僅第一次需要）...
".venv\Scripts\python.exe" -m playwright install chromium || goto :err

echo.
echo 安裝完成！請執行 run.bat 啟動程式。
pause
exit /b 0

:err
echo.
echo 安裝失敗。請確認：
echo   1) 已安裝 Python 3.10 以上版本（python --version）
echo   2) 網路可連線至 PyPI
pause
exit /b 1
