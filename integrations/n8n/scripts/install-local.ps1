[CmdletBinding()]
param(
    [string]$N8nRoot = 'D:\n8n',
    [switch]$Restart
)

$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $PSScriptRoot
$sourceDist = Join-Path $packageRoot 'dist'
$n8nPackage = Join-Path $N8nRoot 'app\node_modules\n8n\package.json'
$startScript = Join-Path $N8nRoot 'scripts\start-n8n.ps1'

if (-not (Test-Path -LiteralPath $n8nPackage)) {
    throw "n8n was not found at $N8nRoot\app. Pass -N8nRoot with the correct installation path."
}
if (-not (Test-Path -LiteralPath $sourceDist)) {
    throw 'Built files are missing. Run npm ci and npm run build in integrations\n8n first.'
}
$version = (Get-Content -LiteralPath $n8nPackage -Raw | ConvertFrom-Json).version
$major = [int]($version.Split('.')[0])
if ($major -lt 2) {
    throw "AutoIXB node targets n8n 2.x; found version $version."
}
if (-not (Test-Path -LiteralPath $startScript)) {
    throw "n8n startup script was not found: $startScript"
}

$customRoot = Join-Path $N8nRoot 'data\.n8n\custom\autoixb'
$backupRoot = Join-Path $N8nRoot 'data\backups\autoixb-node'
New-Item -ItemType Directory -Force -Path $backupRoot, (Split-Path -Parent $customRoot) | Out-Null

if (Test-Path -LiteralPath $customRoot) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backup = Join-Path $backupRoot "autoixb-$stamp"
    Move-Item -LiteralPath $customRoot -Destination $backup
    Write-Output "Previous AutoIXB node files backed up to $backup"
}
New-Item -ItemType Directory -Force -Path $customRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $sourceDist 'nodes') -Destination $customRoot -Recurse -Force
Copy-Item -LiteralPath (Join-Path $sourceDist 'credentials') -Destination $customRoot -Recurse -Force

$listener = Get-NetTCPConnection -LocalPort 5678 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $Restart) {
    if ($listener) {
        Write-Output "AutoIXB node files installed for n8n $version. Restart n8n to load the node."
    } else {
        Write-Output "AutoIXB node files installed for n8n $version. Start n8n to load the node."
    }
    exit 0
}

if ($listener) {
    $n8nPid = [int]$listener.OwningProcess
    $n8nProcess = Get-Process -Id $n8nPid -ErrorAction SilentlyContinue
    if (-not $n8nProcess) {
        throw "Could not resolve the process listening on n8n port 5678 (PID $n8nPid)."
    }
    Stop-Process -Id $n8nPid
    $deadline = (Get-Date).AddSeconds(20)
    do {
        Start-Sleep -Milliseconds 500
        $stillListening = Get-NetTCPConnection -LocalPort 5678 -State Listen -ErrorAction SilentlyContinue
    } while ($stillListening -and (Get-Date) -lt $deadline)
    if ($stillListening) {
        throw 'n8n did not stop within 20 seconds; start it manually after checking the service.'
    }
}

$logPath = Join-Path $N8nRoot 'logs\n8n.log'
$startArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $startScript)
Start-Process -FilePath 'powershell.exe' -ArgumentList $startArgs -WorkingDirectory $N8nRoot -WindowStyle Hidden

$deadline = (Get-Date).AddSeconds(60)
$healthy = $false
do {
    Start-Sleep -Seconds 2
    try {
        $response = Invoke-WebRequest -Uri 'http://127.0.0.1:5678/healthz' -TimeoutSec 2 -UseBasicParsing
        $healthy = $response.StatusCode -eq 200
    } catch {
        $healthy = $false
    }
} while (-not $healthy -and (Get-Date) -lt $deadline)

if (-not $healthy) {
    throw "n8n did not become healthy. Review $logPath and start it manually if needed."
}
Write-Output "AutoIXB files installed and n8n $version restarted successfully."
