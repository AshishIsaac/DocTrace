@echo off
REM Double-click to run: sets up on first use, updates the index, opens the search UI.
setlocal
cd /d "%~dp0"
set "DOCTRACE_NO_PAUSE=1"

if not exist ".venv\.setup-complete" (
    echo First run: setting everything up. This takes a few minutes...
    call "%~dp0setup.bat"
    if errorlevel 1 goto :failed
)

echo.
REM run.py updates the index (only new or changed files), then opens the app - even if indexing fails.
".venv\Scripts\python.exe" run.py %*
REM 130 = stopped with Ctrl+C: a normal way to quit, not an error
if %errorlevel% equ 130 exit /b 0
if errorlevel 1 goto :failed
exit /b 0

:failed
echo.
echo Something went wrong - see the message above. For a full check run:
echo   .venv\Scripts\python doctor.py
pause
exit /b 1
