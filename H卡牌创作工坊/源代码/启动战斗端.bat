@echo off
rem ============================================================
rem  Double-click this file to open the BATTLE client (pygame).
rem  Requires Python 3.10+ and pygame-ce:
rem      python -m pip install -e .
rem  Note 1: keep this file ASCII-only. cmd.exe parses .bat files
rem          with the system code page (GBK on zh-CN Windows), so
rem          UTF-8 Chinese text here would turn into garbled commands.
rem  Note 2: this file must use CRLF line endings - cmd.exe
rem          misparses LF-only files and reports nonsense errors
rem          like "'e' is not recognized as an internal command".
rem ============================================================

cd /d "%~dp0"
echo ============================================
echo   Battle client  ^|  starting...
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] "python" not found on PATH.
    echo Install Python 3.10+ and tick "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

python -c "import pygame" 2>nul
if errorlevel 1 (
    echo [ERROR] pygame-ce is not installed.
    echo Run this first:  python -m pip install -e .
    echo.
    pause
    exit /b 1
)

rem To always fight one specific enemy, change the line below, e.g.
rem     python main.py --battle --enemy cultist
python main.py --battle
set code=%errorlevel%

if not "%code%"=="0" (
    echo.
    echo [ERROR] Battle client exited with code %code%.
    echo Copy the messages above when asking for help.
    pause
)
