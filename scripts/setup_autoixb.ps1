param(
    [switch]$SkipBrowserInstall
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$pythonExecutable = $null
$pythonArgs = @()

Set-Location -LiteralPath $repoRoot

$pyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
if ($pyLauncher) {
    & $pyLauncher.Source -3.12 -c "import sys; print(sys.version)" *> $null
    if ($LASTEXITCODE -eq 0) {
        $pythonExecutable = $pyLauncher.Source
        $pythonArgs = @("-3.12")
    }
}

if (-not $pythonExecutable) {
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $versionText = & $pythonCommand.Source -c "import sys; print('%s.%s' % sys.version_info[:2])"
        if ($LASTEXITCODE -eq 0) {
            $versionParts = $versionText.Trim().Split('.')
            $major = [int]$versionParts[0]
            $minor = [int]$versionParts[1]
            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 10)) {
                $pythonExecutable = $pythonCommand.Source
            }
        }
    }
}

if (-not $pythonExecutable) {
    throw "Python 3.10+ is required. Install Python 3.12 (recommended) and rerun this script."
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Creating project virtual environment..."
    & $pythonExecutable @pythonArgs -m venv $venvPath
    if ($LASTEXITCODE -ne 0) { throw "Could not create .venv (exit $LASTEXITCODE)." }
}

Write-Host "Installing Python dependencies..."
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Could not upgrade pip (exit $LASTEXITCODE)." }
& $venvPython -m pip install -r (Join-Path $repoRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Could not install requirements.txt (exit $LASTEXITCODE)." }

if (-not $SkipBrowserInstall) {
    Write-Host "Installing Playwright Chromium..."
    & $venvPython -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw "Could not install Playwright Chromium (exit $LASTEXITCODE)." }
}

$envExample = Join-Path $repoRoot ".env.example"
$envFile = Join-Path $repoRoot ".env"
if (-not (Test-Path -LiteralPath $envFile)) {
    Copy-Item -LiteralPath $envExample -Destination $envFile
    Write-Host "Created .env from .env.example. Review it before using optional integrations."
} else {
    Write-Host "Keeping existing .env unchanged."
}

Write-Host ""
Write-Host "Setup complete. Start autoIXB with: .\scripts\run_autoixb_web.ps1"
Write-Host "Open http://127.0.0.1:8000/automation/ui"
Write-Host "For phone automation, configure ARTEMIS_ROOT, ARTEMIS_PYTHON, and ADB_PATH in .env."
