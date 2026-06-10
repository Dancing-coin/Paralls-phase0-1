param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$PythonExe = $env:PYTHON_EXE,
    [string]$GodotExe = $env:GODOT_EXE,
    [switch]$SkipGodot
)

$ErrorActionPreference = "Stop"

function Get-BackendHealth {
    try {
        return Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 1
    }
    catch {
        return $null
    }
}

function Get-BackendProcessId {
    $proc = Get-CimInstance Win32_Process |
        Where-Object { $_.CommandLine -match 'uvicorn app\.main:app' } |
        Select-Object -First 1

    if ($null -eq $proc) {
        return $null
    }

    return [int]$proc.ProcessId
}

if (-not $PythonExe) {
    $PythonExe = (Get-Command python -ErrorAction Stop).Source
}

$backendHealth = Get-BackendHealth
if ($backendHealth -and $backendHealth.worktree_root -ne $ProjectRoot) {
    throw "Port 8000 is already occupied by a different backend: $($backendHealth.worktree_root)"
}

$logDir = Join-Path $ProjectRoot ".harness\verification"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$backendProcess = $null
$backendProcessId = $null
if (-not $backendHealth) {
    $backendStdout = Join-Path $logDir "startup-backend.stdout.log"
    $backendStderr = Join-Path $logDir "startup-backend.stderr.log"
    $backendProcess = Start-Process `
        -FilePath $PythonExe `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory (Join-Path $ProjectRoot "backend") `
        -PassThru `
        -RedirectStandardOutput $backendStdout `
        -RedirectStandardError $backendStderr

    $deadline = (Get-Date).AddSeconds(20)
    do {
        Start-Sleep -Milliseconds 250
        $backendHealth = Get-BackendHealth
        if ($backendHealth -and $backendHealth.worktree_root -eq $ProjectRoot) {
            break
        }
    } while ((Get-Date) -lt $deadline)

    if (-not $backendHealth -or $backendHealth.worktree_root -ne $ProjectRoot) {
        throw "Backend did not become healthy on port 8000 within 20 seconds. Logs: $backendStdout, $backendStderr"
    }
    $backendProcessId = $backendProcess.Id
}
else {
    $backendProcessId = Get-BackendProcessId
}

Write-Output "Backend ready: $($backendHealth.status) @ $($backendHealth.worktree_root)"
if ($backendProcessId) {
    Write-Output "Backend process id: $backendProcessId"
}

if ($SkipGodot) {
    return
}

if (-not $GodotExe) {
    Write-Output "GODOT_EXE is not set, skipping Godot launch."
    return
}

if (-not (Test-Path $GodotExe)) {
    throw "Godot executable not found: $GodotExe"
}

$godotProcess = Start-Process `
    -FilePath $GodotExe `
    -ArgumentList @("--path", $ProjectRoot) `
    -WorkingDirectory $ProjectRoot `
    -PassThru

Write-Output "Godot launched: process id $($godotProcess.Id)"
