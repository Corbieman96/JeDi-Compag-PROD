@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ============================================================
REM JeDiS Server - Zastaveni
REM ============================================================
REM Uvicorn s --reload: na portu nasloucha child, rodic znovu spousti
REM worker -> taskkill jen na PID z netstat nestaci. bere se rodic
REM a ukoncuje se cely strom (/T).
REM Get-NetTCPConnection je nezavisly na lokalizaci netstat.
REM ============================================================

echo.
echo ============================================================
echo   JeDiS Server - Zastavuji...
echo ============================================================
echo.

cd /d "%~dp0"
echo [INFO] Pracovni adresar: %CD%

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

if not defined PORT set "PORT=8000"

echo [INFO] Hledam proces na portu: %PORT%

REM Jednoradkovy PowerShell: spolehliveisi nez vicradkove escapovani uvozovek v CMD.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$port=%PORT%; $conns=@(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue); if ($conns.Count -eq 0) { Write-Host '[OK] Na portu' $port 'nic nebezi.'; exit 0 }; $listenPid=[int]($conns | Select-Object -First 1 -ExpandProperty OwningProcess); $proc=Get-CimInstance Win32_Process -Filter ('ProcessId=' + $listenPid); $parent=0; if ($null -ne $proc) { $parent=[int]$proc.ParentProcessId }; $killPid=$listenPid; if ($parent -gt 0) { $killPid=$parent }; Write-Host ('[INFO] Nasloucha PID ' + $listenPid + ', ukoncuji PID ' + $killPid + ' (strom /T)...'); & taskkill.exe /PID $killPid /T /F; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Write-Host ('[OK] Server na portu ' + $port + ' zastaven.'); exit 0"

if errorlevel 1 (
  echo [ERROR] Nepodarilo se spolehlive ukoncit server.
  echo        Zkuste jako spravce, pripadne Task Manager ^(Python / uvicorn^).
  echo.
  pause
  exit /b 1
)

echo.
pause
endlocal
