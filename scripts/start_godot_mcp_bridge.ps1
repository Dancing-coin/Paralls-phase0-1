param(
    [string]$ServerDir = "E:\User\Documents\tools\godot-mcp-pro-v1.14.1\server"
)

$ErrorActionPreference = "Stop"

function Get-BridgeProcess {
    Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
        Where-Object {
            $_.CommandLine -match 'godot-mcp-pro-v1\.14\.1[\\/].*build[\\/]index\.js' -or
            $_.CommandLine -match '(^|["\s])build[\\/]index\.js($|["\s])'
        }
}

function Get-ListeningPorts {
    $ports = 6505..6514
    $lines = netstat -ano -p TCP | Select-String '127\.0\.0\.1:65(0[5-9]|1[0-4])'
    $listening = @()
    foreach ($line in $lines) {
        $text = $line.ToString()
        if ($text -match '127\.0\.0\.1:(\d+)\s+0\.0\.0\.0:0\s+LISTENING') {
            $listening += [int]$matches[1]
        }
    }
    $listening | Sort-Object -Unique
}

if (-not (Test-Path $ServerDir)) {
    throw "Godot MCP server directory not found: $ServerDir"
}

$node = (Get-Command node -ErrorAction Stop).Source
$existing = @(Get-BridgeProcess)
if ($existing.Count -gt 0) {
    $ports = Get-ListeningPorts
    $pids = ($existing | ForEach-Object { $_.ProcessId }) -join ","
    Write-Output ("godot-mcp-pro bridge already running. pid={0} ports={1}" -f $pids, ($ports -join ","))
    exit 0
}

$listeningBefore = Get-ListeningPorts
if ($listeningBefore.Count -gt 0) {
    Write-Output ("godot-mcp-pro bridge already listening on ports={0}" -f ($listeningBefore -join ","))
    exit 0
}

$proc = Start-Process -FilePath $node -ArgumentList 'build/index.js' -WorkingDirectory $ServerDir -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 3

$started = @(Get-BridgeProcess)
$portsAfter = Get-ListeningPorts
if ($started.Count -eq 0 -or $portsAfter.Count -eq 0) {
    throw "Failed to start godot-mcp-pro bridge."
}

$startedPids = ($started | ForEach-Object { $_.ProcessId }) -join ","
Write-Output ("godot-mcp-pro bridge started. pid={0} ports={1}" -f $startedPids, ($portsAfter -join ","))
