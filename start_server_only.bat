@echo off
setlocal ENABLEDELAYEDEXPANSION

echo.
echo ============================================================
echo   JeDiS - Start serveru
echo ============================================================
echo.

cd /d "%~dp0"
echo [INFO] Pracovni adresar: %CD%
set "PROJECT_ROOT=%CD%"

set "VENV_DIR=.venv"

REM Nacist .env (kvuli HOST/PORT a pripadnym cestam)
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    set "line=%%a"
    if not "!line!"=="" (
      if not "!line:~0,1!"=="#" (
        set "%%a=%%b"
      )
    )
  )
)

REM Data cesty: pokud nejsou v .env, vzit ulozeny target path
if not defined DATA_DIR (
  if exist ".data_target_path.txt" (
    set /p "DATA_DIR="<".data_target_path.txt"
  )
)

if not defined DATA_DIR (
  set "DATA_DIR=%CD%\%VENV_DIR%\data"
)

if not defined DATABASE_URL (
  echo [ERROR] DATABASE_URL neni definovano v souboru .env.
  echo         Nastavte DATABASE_URL ve formatu sqlite:///absolutni/cesta/k/app.db
  exit /b 1
)

if /I "%DATABASE_URL%"=="sqlite:///app/data/app.db" (
  echo [ERROR] DATABASE_URL nesmi smerovat na sqlite:///app/data/app.db
  echo         Pouzijte hodnotu DATABASE_URL z .env - absolutni cesta k app.db
  exit /b 1
)

if not defined ACTIVITY_DATA_DIR set "ACTIVITY_DATA_DIR=%DATA_DIR%"

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo [ERROR] Virtualni prostredi %VENV_DIR% neexistuje.
  echo        Nejdriv spuste install_server.bat
  echo.
  pause
  exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
  echo [ERROR] Nepodarilo se aktivovat virtualni prostredi.
  pause
  exit /b 1
)

REM Nastaveni serveru
if not defined HOST set "HOST=192.168.1.18"
if not defined PORT set "PORT=8000"

if not "%~1"=="" set "HOST=%~1"
if not "%~2"=="" set "PORT=%~2"

echo.
echo ============================================================
echo   Server bezi na: http://%HOST%:%PORT%
echo   PROJECT_ROOT: %PROJECT_ROOT%
echo   DATA_DIR: %DATA_DIR%
echo ============================================================
echo.

"%PROJECT_ROOT%\%VENV_DIR%\Scripts\python.exe" -m uvicorn config.asgi:application --app-dir "%PROJECT_ROOT%" --host %HOST% --port %PORT% --reload

endlocal
pause
