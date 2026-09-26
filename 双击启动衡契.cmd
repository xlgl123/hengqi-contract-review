@echo off
setlocal
title Hengqi Contract Review

set "PROJECT_ROOT=%~dp0"
if not defined HENGQI_RUNTIME_DIR (
  if exist "F:\" (
    set "HENGQI_RUNTIME_DIR=F:\HengqiContractReview"
  ) else (
    set "HENGQI_RUNTIME_DIR=%LOCALAPPDATA%\HengqiContractReview"
  )
)
set "VENV_PYTHON=%HENGQI_RUNTIME_DIR%\venv\Scripts\python.exe"
set "READY_MARKER=%HENGQI_RUNTIME_DIR%\venv\.hengqi-ready"
set "PIP_CACHE_DIR=%HENGQI_RUNTIME_DIR%\pip-cache"
set "DATABASE_PATH=%HENGQI_RUNTIME_DIR%\data\reviews.db"
set "AI_CREDENTIAL_PATH=%HENGQI_RUNTIME_DIR%\data\ai-settings.dpapi"

if exist "%VENV_PYTHON%" goto runtime_ready

where py >nul 2>&1
if not errorlevel 1 (
  py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
  if not errorlevel 1 (
    set "BOOTSTRAP_PYTHON=py -3"
    goto create_runtime
  )
)
where python >nul 2>&1
if not errorlevel 1 (
  python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
  if not errorlevel 1 (
    set "BOOTSTRAP_PYTHON=python"
    goto create_runtime
  )
)

echo [ERROR] Python 3.11 or newer was not found.
echo Install Python 3.11 or newer from https://www.python.org/downloads/
echo During installation, select "Add Python to PATH", then run this file again.
pause
exit /b 1

:create_runtime
echo Preparing the private Python environment for first use...
if not exist "%HENGQI_RUNTIME_DIR%" mkdir "%HENGQI_RUNTIME_DIR%"
%BOOTSTRAP_PYTHON% -m venv "%HENGQI_RUNTIME_DIR%\venv"
if errorlevel 1 (
  echo [ERROR] Failed to create the Python environment.
  pause
  exit /b 1
)

:runtime_ready
if exist "%READY_MARKER%" goto start_app
echo Installing required packages. The first launch needs an internet connection...
"%VENV_PYTHON%" -m pip install --disable-pip-version-check -r "%PROJECT_ROOT%backend\requirements.txt"
if errorlevel 1 (
  echo [ERROR] Dependency installation failed. Check the network and try again.
  pause
  exit /b 1
)
type nul > "%READY_MARKER%"

:start_app
echo Starting Hengqi Contract Review. Please wait...
"%VENV_PYTHON%" "%PROJECT_ROOT%scripts\local_server.py" status >nul 2>&1
if not errorlevel 1 (
  echo Hengqi is already running.
  start "" "http://127.0.0.1:8765"
  exit /b 0
)

echo.
echo IMPORTANT: Keep this window open while using the web app.
echo Closing this window will stop the local server.
echo.
"%VENV_PYTHON%" "%PROJECT_ROOT%scripts\local_server.py" serve
if errorlevel 1 (
  echo.
  echo The local server stopped with an error. Capture the message above.
  pause
  exit /b 1
)
