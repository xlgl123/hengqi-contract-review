@echo off
setlocal
set "PYTHON=F:\Codex\venvs\tianhe-contract-mvp\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
"%PYTHON%" "%~dp0scripts\local_server.py" stop
if errorlevel 1 pause

