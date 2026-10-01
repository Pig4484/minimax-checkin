@echo off
rem ============================================================================
rem  MiniMax Check-in — 一鍵建置安裝程式
rem
rem  用法：
rem    build.bat                 完整版（內建 Chromium，安裝後免連網下載）
rem    build.bat lite            精簡版（不安裝瀏覽器核心，安裝檔較小）
rem    build.bat --no-installer  只產生執行檔目錄
rem
rem  輸出：
rem    dist\MinimaxCheckin\                                     可直接執行的程式目錄
rem    dist\installer\MiniMaxCheckin-Setup-<版本>-<flavor>.exe   安裝包（含卸載功能）
rem    dist\portable\MiniMaxCheckin-Portable-<版本>-<flavor>.zip 免安裝版（解壓即用）
rem
rem  首次執行會自動準備：
rem    * PyInstaller（若缺少會透過 uv/pip 安裝）
rem    * Inno Setup 6 可攜版（下載到 %LOCALAPPDATA%，不污染系統）
rem ============================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo  MiniMax Check-in - 建置安裝程式
echo ============================================================

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] 找不到 .venv，先建立執行環境...
    call setup.bat || goto :err
)

set "PY=.venv\Scripts\python.exe"

echo [1/4] 檢查 PyInstaller...
"%PY%" -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo       安裝 PyInstaller...
    where uv >nul 2>nul
    if !errorlevel!==0 (
        uv pip install --python "%PY%" pyinstaller || goto :err
    ) else (
        "%PY%" -m pip install pyinstaller || goto :err
    )
)

echo [2/4] 檢查 Inno Setup...
"%PY%" build_tools\bootstrap_inno.py || echo       （稍後仍會再嘗試）

echo [3/4] 執行打包與建立安裝程式...
"%PY%" build_tools\build.py %*

if errorlevel 1 goto :err

echo.
echo ============================================================
echo  建置完成！輸出在 dist\ 目錄
echo ============================================================
echo [安裝包]
dir /b "dist\installer\*.exe" 2>nul
echo [免安裝版]
dir /b "dist\portable\*.zip" 2>nul
pause
exit /b 0

:err
echo.
echo 建置失敗。請確認：
echo   1) 已執行 setup.bat 完成環境安裝
echo   2) 磁碟剩餘空間至少 3GB
echo   3) 網路可連線（下載 Inno Setup）
pause
exit /b 1