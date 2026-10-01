@echo off
rem === MiniMax 自動簽到：啟動程式 ===
rem 用法：
rem   run.bat              以無主控台模式啟動（建議，雙擊即可）
rem   run.bat --console    保留主控台，方便看錯誤訊息
rem   run.bat --minimized  啟動後直接縮到系統匣
setlocal
cd /d "%~dp0"

set "PYW=%~dp0.venv\Scripts\pythonw.exe"
set "PY=%~dp0.venv\Scripts\python.exe"
set "ENTRY=%~dp0main.py"

if not exist "%PY%" (
    echo 尚未安裝執行環境，請先執行 setup.bat
    pause
    exit /b 1
)

if "%~1"=="--console" (
    shift
    "%PY%" "%ENTRY%" %*
    pause
    exit /b 0
)

start "" "%PYW%" "%ENTRY%" %*
exit /b 0

