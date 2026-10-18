param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,
    [string]$PythonExe = "",
    [ValidateRange(1, 300)]
    [int]$RestartDelaySeconds = 5
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path

function Read-DotEnv([string]$Path) {
    $values = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $values
    }

    foreach ($rawLine in Get-Content -LiteralPath $Path) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            continue
        }
        $key, $value = $line.Split("=", 2)
        $key = $key.Trim()
        $value = $value.Trim()
        if ($value.Length -ge 2 -and $value[0] -eq $value[$value.Length - 1] -and $value[0] -in @('"', "'")) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        if ($key) {
            $values[$key] = $value
        }
    }
    return $values
}

$config = Read-DotEnv (Join-Path $ProjectRoot ".env")
if (-not $PythonExe -and $config.ContainsKey("PYTHON_EXE")) {
    $PythonExe = $config["PYTHON_EXE"]
}
if (-not $PythonExe) {
    $localPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    $sharedPython = Join-Path (Split-Path $ProjectRoot -Parent) ".venv\Scripts\python.exe"
    $PythonExe = if (Test-Path -LiteralPath $localPython) { $localPython } else { $sharedPython }
}
if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python nebyl nalezen: $PythonExe"
}

$listenHost = if ($config.ContainsKey("HOST")) { $config["HOST"] } else { "127.0.0.1" }
$listenPort = if ($config.ContainsKey("PORT")) { [int]$config["PORT"] } else { 8000 }
$environment = if ($config.ContainsKey("JEDIS_ENVIRONMENT")) { $config["JEDIS_ENVIRONMENT"] } else { "UNKNOWN" }

$logDir = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$stdoutLog = Join-Path $logDir "uvicorn.out.log"
$stderrLog = Join-Path $logDir "uvicorn.err.log"
$supervisorLog = Join-Path $logDir "supervisor.log"
$env:PYTHONUNBUFFERED = "1"

while ($true) {
    $startedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $supervisorLog -Encoding UTF8 -Value "$startedAt start $environment http://${listenHost}:$listenPort"
    Push-Location $ProjectRoot
    try {
        # Windows PowerShell 5.1 converts native stderr output into ErrorRecord
        # objects. With ErrorActionPreference=Stop, Uvicorn's normal startup
        # messages on stderr terminated the invocation immediately. Start the
        # native process explicitly so stderr can be logged without being
        # interpreted as a PowerShell exception.
        $arguments = @(
            "-m", "uvicorn", "config.asgi:application",
            "--app-dir", $ProjectRoot,
            "--host", $listenHost,
            "--port", [string]$listenPort
        )
        $process = Start-Process `
            -FilePath $PythonExe `
            -ArgumentList $arguments `
            -WorkingDirectory $ProjectRoot `
            -RedirectStandardOutput $stdoutLog `
            -RedirectStandardError $stderrLog `
            -NoNewWindow `
            -PassThru `
            -Wait
        $exitCode = $process.ExitCode
    }
    catch {
        $exitCode = 1
        Add-Content -LiteralPath $stderrLog -Encoding UTF8 -Value $_.Exception.ToString()
    }
    finally {
        Pop-Location
    }

    $stoppedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $supervisorLog -Encoding UTF8 -Value "$stoppedAt exit=$exitCode restart_in=${RestartDelaySeconds}s"
    Start-Sleep -Seconds $RestartDelaySeconds
}
