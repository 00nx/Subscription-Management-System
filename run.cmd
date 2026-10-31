@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem ============================================================================
rem  Brightloop, the easy way. Needs ONLY Python 3.12+ and Node.js 20+.
rem  No PostgreSQL needed: the data lives in one SQLite file (brightloop-demo.db).
rem  Redis is optional (without it there is no background worker/scheduler).
rem
rem    run.cmd            first run: set everything up, then start the app
rem    run.cmd setup      install + create database + demo data, then stop
rem    run.cmd razorpay   check the Razorpay setup step by step (run in a 2nd window while the app runs)
rem    run.cmd seed       reload demo data
rem    run.cmd --no-ngrok start without the ngrok tunnel (by default it starts if ngrok is installed)
rem  Other database: run-postgres.cmd (PostgreSQL).
rem  Press Ctrl+C in this window to stop the app.
rem ============================================================================

set "DBLCLICK="
echo %cmdcmdline% | find /i "/c" >nul && set "DBLCLICK=1"

set "PYCMD="
py -3 --version >nul 2>&1 && set "PYCMD=py -3"
if not defined PYCMD python --version >nul 2>&1 && set "PYCMD=python"
if not defined PYCMD (
  echo [ERROR] Python was not found. Install Python 3.12+ from https://www.python.org/downloads/
  echo         and tick "Add python.exe to PATH" in the installer, then run this again.
  set "RC=1"
  goto done
)

%PYCMD% dev.py %*
set "RC=%errorlevel%"

:done
echo.
if "%RC%"=="0" (echo Finished OK.) else (echo Finished with errors ^(exit code %RC%^). Scroll up to read the message.)
if defined DBLCLICK (
  echo Press any key to close this window...
  pause >nul
)
exit /b %RC%
