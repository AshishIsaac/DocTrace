@echo off
REM One-time setup for Windows. Finds Python 3.10+ and runs scripts\bootstrap.py
REM Options: --yes (install all extras)  --no-extras  --cpu  --gpu  --gdrive
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PY="
for %%V in (3.12 3.13 3.11 3.10) do (
    if not defined PY (
        py -%%V -c "import sys" >nul 2>nul && set "PY=py -%%V"
    )
)
if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo Python 3.10 or newer was not found.
    where winget >nul 2>nul
    if !errorlevel! equ 0 (
        choice /C YN /M "Install Python 3.12 now with winget"
        if !errorlevel! equ 1 (
            winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
            py -3.12 -c "import sys" >nul 2>nul && set "PY=py -3.12"
            REM this window's PATH predates the install, so also look where winget puts it
            if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe""
            if not defined PY if exist "%ProgramFiles%\Python312\python.exe" set "PY="%ProgramFiles%\Python312\python.exe""
        )
    )
)
if not defined PY (
    echo.
    echo Please install Python 3.12 from https://www.python.org/downloads/
    echo ^(tick "Add python.exe to PATH"^), then run setup.bat again.
    if not defined DOCTRACE_NO_PAUSE pause
    exit /b 1
)

%PY% scripts\bootstrap.py %*
set "RC=%errorlevel%"
if not defined DOCTRACE_NO_PAUSE pause
exit /b %RC%
