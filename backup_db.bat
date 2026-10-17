@echo off
setlocal ENABLEDELAYEDEXPANSION
cd /d "%~dp0"

if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    set "line=%%a"
    if not "!line!"=="" if not "!line:~0,1!"=="#" set "%%a=%%b"
  )
)

if not defined PYTHON_EXE (
  if exist "%CD%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
  ) else (
    set "PYTHON_EXE=%CD%\..\.venv\Scripts\python.exe"
  )
)

if not exist "%PYTHON_EXE%" (
  echo [ERROR] Python nebyl nalezen: %PYTHON_EXE%
  exit /b 1
)

"%PYTHON_EXE%" manage.py backup_db
exit /b %ERRORLEVEL%
