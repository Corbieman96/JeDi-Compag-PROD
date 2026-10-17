@echo off
setlocal ENABLEDELAYEDEXPANSION

cd /d "%~dp0"
set "PROJECT_ROOT=%CD%"

REM Nacist lokalni konfiguraci prostredi.
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    set "line=%%a"
    if not "!line!"=="" if not "!line:~0,1!"=="#" set "%%a=%%b"
  )
)

if not defined PYTHON_EXE (
  if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
  ) else (
    set "PYTHON_EXE=%PROJECT_ROOT%\..\.venv\Scripts\python.exe"
  )
)

if not exist "%PYTHON_EXE%" (
  echo [ERROR] Python nebyl nalezen: %PYTHON_EXE%
  exit /b 1
)

if not defined DATABASE_URL (
  echo [ERROR] DATABASE_URL neni definovano v .env.
  exit /b 1
)

if not defined DATA_DIR set "DATA_DIR=%PROJECT_ROOT%\data"
if not defined ACTIVITY_DATA_DIR set "ACTIVITY_DATA_DIR=%DATA_DIR%"
if not defined HOST set "HOST=192.168.1.18"
if not defined PORT set "PORT=8000"

if not "%~1"=="" set "HOST=%~1"
if not "%~2"=="" set "PORT=%~2"

echo [INFO] JeDiS startuje bez automatickeho reloadu.
echo [INFO] Prostredi: %JEDIS_ENVIRONMENT%
echo [INFO] URL: http://%HOST%:%PORT%
echo [INFO] Projekt: %PROJECT_ROOT%

"%PYTHON_EXE%" -m uvicorn config.asgi:application --app-dir "%PROJECT_ROOT%" --host "%HOST%" --port "%PORT%"
set "EXIT_CODE=%ERRORLEVEL%"
echo [INFO] Uvicorn skoncil s kodem %EXIT_CODE%.
exit /b %EXIT_CODE%
