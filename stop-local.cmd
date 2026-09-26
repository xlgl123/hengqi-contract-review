@echo off
setlocal
if not defined HENGQI_RUNTIME_DIR (
  if exist "F:\" (
    set "HENGQI_RUNTIME_DIR=F:\HengqiContractReview"
  ) else (
    set "HENGQI_RUNTIME_DIR=%LOCALAPPDATA%\HengqiContractReview"
  )
)
set "PYTHON=%HENGQI_RUNTIME_DIR%\venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
"%PYTHON%" "%~dp0scripts\local_server.py" stop
if errorlevel 1 pause
