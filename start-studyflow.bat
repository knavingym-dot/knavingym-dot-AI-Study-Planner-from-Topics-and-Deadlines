@echo off
setlocal
cd /d "%~dp0"

for %%V in (313 312 311 310) do (
  if not defined STUDYFLOW_PYTHON if exist "%LocalAppData%\Programs\Python\Python%%V\python.exe" set "STUDYFLOW_PYTHON=%LocalAppData%\Programs\Python\Python%%V\python.exe"
)
if defined STUDYFLOW_PYTHON (
  start "Studyflow backend" /D "%~dp0" "%STUDYFLOW_PYTHON%" server.py
) else (
  where py >nul 2>&1
  if errorlevel 1 (
    echo Python 3.10 or newer is required. Install Python, then run this file again.
    pause
    exit /b 1
  )
  start "Studyflow backend" /D "%~dp0" py -3 server.py
)

timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:8000
