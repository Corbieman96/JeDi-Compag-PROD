param(
    [ValidateSet("Install", "Remove", "Start", "Stop", "Status")]
    [string]$Action = "Status",
    [string]$BaseRoot = "C:\Jedi_2_0",
    [string]$ServiceUser = "$env:USERDOMAIN\$env:USERNAME",
    [switch]$RunAsSystem
)

$ErrorActionPreference = "Stop"
$BaseRoot = (Resolve-Path -LiteralPath $BaseRoot).Path
$pythonExe = Join-Path $BaseRoot ".venv\Scripts\python.exe"
$powershellExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

$instances = @(
    [PSCustomObject]@{
        TaskName = "JeDiS PROD"
        ProjectRoot = Join-Path $BaseRoot "JeDis-PROD"
        Port = 8000
        FirewallRule = "JeDiS PROD TCP 8000"
    },
    [PSCustomObject]@{
        TaskName = "JeDiS TEST"
        ProjectRoot = Join-Path $BaseRoot "JeDis-TEST"
        Port = 8001
        FirewallRule = "JeDiS TEST TCP 8001"
    }
)

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Tuto akci spustte v PowerShellu otevrenem jako spravce."
    }
}

function Get-TaskStateRows {
    foreach ($instance in $instances) {
        $task = Get-ScheduledTask -TaskName $instance.TaskName -ErrorAction SilentlyContinue
        if (-not $task) {
            [PSCustomObject]@{ Task = $instance.TaskName; State = "Not installed"; LastRun = $null; Result = $null }
            continue
        }
        $info = Get-ScheduledTaskInfo -TaskName $instance.TaskName
        [PSCustomObject]@{ Task = $instance.TaskName; State = $task.State; LastRun = $info.LastRunTime; Result = $info.LastTaskResult }
    }
}

function Stop-InstanceRuntime($instance) {
    Stop-ScheduledTask -TaskName $instance.TaskName -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1

    # Start-Process can outlive its Scheduled Task host.  The ports below are
    # dedicated to these instances, so remove a stale Python listener before a
    # later Start attempts to bind the same address again.
    $listeners = Get-NetTCPConnection -LocalPort $instance.Port -State Listen -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        $process = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
        if (-not $process) {
            continue
        }
        if ($process.ProcessName -notin @("python", "pythonw")) {
            throw "Port $($instance.Port) pouziva neocekavany proces $($process.ProcessName) (PID $($process.Id))."
        }
        Stop-Process -Id $process.Id -Force
    }

    $deadline = (Get-Date).AddSeconds(10)
    do {
        $remaining = Get-NetTCPConnection -LocalPort $instance.Port -State Listen -ErrorAction SilentlyContinue
        if (-not $remaining) {
            return
        }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)

    throw "Port $($instance.Port) se nepodarilo uvolnit."
}

switch ($Action) {
    "Install" {
        Assert-Administrator
        if (-not (Test-Path -LiteralPath $pythonExe)) {
            throw "Sdilene Python prostredi nebylo nalezeno: $pythonExe"
        }
        foreach ($instance in $instances) {
            if (-not (Test-Path -LiteralPath $instance.ProjectRoot)) {
                throw "Projekt nebyl nalezen: $($instance.ProjectRoot)"
            }
        }

        $credential = $null
        if (-not $RunAsSystem) {
            $credential = Get-Credential -UserName $ServiceUser -Message "Ucet pro obe ulohy JeDiS (doporuceno kvuli MS Excel tisku)"
        }
        $runtimeIdentity = if ($RunAsSystem) { "NT AUTHORITY\SYSTEM" } else { $credential.UserName }

        foreach ($instance in $instances) {
            $envPath = Join-Path $instance.ProjectRoot ".env"
            & icacls.exe $envPath "/inheritance:r" "/grant:r" "${runtimeIdentity}:(F)" "*S-1-5-18:(F)" "*S-1-5-32-544:(F)" | Out-Null
            if ($LASTEXITCODE -ne 0) {
                throw "Nepodarilo se omezit pristup k $envPath"
            }

            $runner = Join-Path $instance.ProjectRoot "scripts\run_server_task.ps1"
            $arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}" -ProjectRoot "{1}" -PythonExe "{2}"' -f $runner, $instance.ProjectRoot, $pythonExe
            $taskAction = New-ScheduledTaskAction -Execute $powershellExe -Argument $arguments -WorkingDirectory $instance.ProjectRoot
            $trigger = New-ScheduledTaskTrigger -AtStartup
            $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 10 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

            if ($RunAsSystem) {
                $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
                $definition = New-ScheduledTask -Action $taskAction -Trigger $trigger -Settings $settings -Principal $principal -Description "$($instance.TaskName) Uvicorn"
                Register-ScheduledTask -TaskName $instance.TaskName -InputObject $definition -Force | Out-Null
            }
            else {
                $definition = New-ScheduledTask -Action $taskAction -Trigger $trigger -Settings $settings -Description "$($instance.TaskName) Uvicorn"
                $password = $credential.GetNetworkCredential().Password
                Register-ScheduledTask -TaskName $instance.TaskName -InputObject $definition -User $credential.UserName -Password $password -Force | Out-Null
            }

            if (-not (Get-NetFirewallRule -DisplayName $instance.FirewallRule -ErrorAction SilentlyContinue)) {
                New-NetFirewallRule -DisplayName $instance.FirewallRule -Direction Inbound -Action Allow -Protocol TCP -LocalPort $instance.Port -Profile Any -RemoteAddress LocalSubnet | Out-Null
            }
        }
        Get-TaskStateRows | Format-Table -AutoSize
    }
    "Remove" {
        Assert-Administrator
        foreach ($instance in $instances) {
            Stop-InstanceRuntime $instance
            Unregister-ScheduledTask -TaskName $instance.TaskName -Confirm:$false -ErrorAction SilentlyContinue
            Remove-NetFirewallRule -DisplayName $instance.FirewallRule -ErrorAction SilentlyContinue
        }
        Get-TaskStateRows | Format-Table -AutoSize
    }
    "Start" {
        foreach ($instance in $instances) {
            Start-ScheduledTask -TaskName $instance.TaskName
        }
        Start-Sleep -Seconds 2
        Get-TaskStateRows | Format-Table -AutoSize
    }
    "Stop" {
        Assert-Administrator
        foreach ($instance in $instances) {
            Stop-InstanceRuntime $instance
        }
        Start-Sleep -Seconds 2
        Get-TaskStateRows | Format-Table -AutoSize
    }
    "Status" {
        Get-TaskStateRows | Format-Table -AutoSize
    }
}
