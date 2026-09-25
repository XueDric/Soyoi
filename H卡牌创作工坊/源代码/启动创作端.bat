@echo off
rem ============================================================
rem  Double-click this file to open the CARD CREATOR (Tkinter).
rem  Requires Python 3.10+ on PATH (tkinter ships with Python).
rem  Note 1: keep this file ASCII-only. cmd.exe parses .bat files
rem          with the system code page (GBK on zh-CN Windows), so
rem          UTF-8 Chinese text here would turn into garbled commands.
rem  Note 2: this file must use CRLF line endings - cmd.exe
rem          misparses LF-only files and reports nonsense errors
rem          like "'e' is not recognized as an internal command".
rem ============================================================

cd /d "%~dp0"
echo ============================================
echo   Card Creator  ^|  starting...
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

python -c "import tkinter" 2>nul
if errorlevel 1 (
    echo [ERROR] This Python has no tkinter, cannot show the GUI.
    echo Reinstall Python with the tcl/tk option enabled.
    echo.
    pause
    exit /b 1
)

python main.py
set code=%errorlevel%

if not "%code%"=="0" (
    echo.
    echo [ERROR] Creator exited with code %code%.
    echo Copy the messages above when asking for help.
    pause
)
