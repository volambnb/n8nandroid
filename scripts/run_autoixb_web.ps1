$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = $env:AUTOIXB_PYTHON
$pythonArgs = @()
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
$pyCommand = Get-Command py.exe -ErrorAction SilentlyContinue

if (-not $python) {
    if (Test-Path -LiteralPath $venvPython) {
        $python = $venvPython
    } elseif ($pythonCommand) {
        $python = $pythonCommand.Source
    } elseif ($pyCommand) {
        $python = $pyCommand.Source
        $pythonArgs = @("-3.12")
    }
}
$entryPoint = Join-Path $repoRoot "main.py"
$logDirectory = Join-Path $repoRoot "logs"
$consoleLog = Join-Path $logDirectory "autoixb-web-console.log"

if (-not $python) {
    throw "Python was not found. Run scripts/setup_autoixb.ps1 or set AUTOIXB_PYTHON."
}
if (-not (Test-Path -LiteralPath $entryPoint)) {
    throw "autoIXB entry point was not found: $entryPoint"
}

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
Set-Location -LiteralPath $repoRoot
"[$(Get-Date -Format o)] Starting autoIXB web service." | Add-Content -LiteralPath $consoleLog -Encoding UTF8

# Windows PowerShell 5 treats native stderr output as an error record. The
# service logs normally write to stderr, so keep those records from terminating
# the wrapper before Python has finished starting.
$ErrorActionPreference = "Continue"
& $python @pythonArgs -u $entryPoint *>> $consoleLog
$exitCode = $LASTEXITCODE

"[$(Get-Date -Format o)] autoIXB web service exited with code $exitCode." | Add-Content -LiteralPath $consoleLog -Encoding UTF8
exit $exitCode
