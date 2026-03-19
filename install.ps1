#Requires -Version 5.1
<#
.SYNOPSIS
    JARVIS one-line installer for Windows.

.DESCRIPTION
    Downloads and installs JARVIS voice assistant.
    Installs uv (Python package manager) if not present.
    Installs Python 3.12+ via uv if not present.
    Clones the repo, installs dependencies, and adds jarvis to PATH.

.EXAMPLE
    irm https://raw.githubusercontent.com/MiguelAguiarDEV/jarvis/main/install.ps1 | iex

.NOTES
    - Requires internet connection
    - Requires Windows 10/11
    - Does NOT require admin rights (installs to user directory)
#>

$ErrorActionPreference = "Stop"
$JARVIS_DIR = "$env:USERPROFILE\.jarvis"
$JARVIS_BIN = "$env:USERPROFILE\.local\bin"
$REPO_URL = "https://github.com/MiguelAguiarDEV/jarvis.git"

function Write-Step {
    param([string]$Message)
    Write-Host "`n[JARVIS] " -ForegroundColor Cyan -NoNewline
    Write-Host $Message
}

function Write-Ok {
    param([string]$Message)
    Write-Host "  OK: " -ForegroundColor Green -NoNewline
    Write-Host $Message
}

function Write-Warn {
    param([string]$Message)
    Write-Host "  WARN: " -ForegroundColor Yellow -NoNewline
    Write-Host $Message
}

function Write-Fail {
    param([string]$Message)
    Write-Host "  FAIL: " -ForegroundColor Red -NoNewline
    Write-Host $Message
}

# --- Step 1: Check/Install uv ---
Write-Step "Checking for uv..."
$uvPath = Get-Command uv -ErrorAction SilentlyContinue
if ($uvPath) {
    $uvVersion = & uv --version 2>&1
    Write-Ok "uv found: $uvVersion"
} else {
    Write-Step "Installing uv..."
    try {
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")
        $uvVersion = & uv --version 2>&1
        Write-Ok "uv installed: $uvVersion"
    } catch {
        Write-Fail "Failed to install uv: $_"
        Write-Host "  Install manually: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    }
}

# --- Step 2: Clone or update repo ---
Write-Step "Setting up JARVIS in $JARVIS_DIR..."
if (Test-Path "$JARVIS_DIR\.git") {
    Write-Ok "JARVIS directory exists, pulling latest..."
    Push-Location $JARVIS_DIR
    & git pull --ff-only 2>&1 | Out-Null
    Pop-Location
} else {
    if (Test-Path $JARVIS_DIR) {
        Remove-Item -Recurse -Force $JARVIS_DIR
    }
    Write-Step "Cloning repository..."
    & git clone $REPO_URL $JARVIS_DIR 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to clone repository. Is git installed?"
        Write-Host "  Install git: https://git-scm.com/download/win"
        exit 1
    }
    Write-Ok "Repository cloned"
}

# --- Step 3: Install Python + dependencies ---
Write-Step "Installing dependencies..."
Push-Location $JARVIS_DIR
try {
    & uv sync --extra dev --extra audio 2>&1 | Out-Null
    Write-Ok "Dependencies installed"
} catch {
    Write-Warn "Some dependencies may have failed (PyAudio requires portaudio)"
    & uv sync --extra dev 2>&1 | Out-Null
    Write-Ok "Core dependencies installed (audio optional)"
}
Pop-Location

# --- Step 4: Create jarvis command ---
Write-Step "Creating jarvis command..."
if (-not (Test-Path $JARVIS_BIN)) {
    New-Item -ItemType Directory -Path $JARVIS_BIN -Force | Out-Null
}

$jarvisCmd = @"
@echo off
pushd "$JARVIS_DIR"
uv run python -m jarvis %*
popd
"@

$jarvisCmdPath = "$JARVIS_BIN\jarvis.cmd"
Set-Content -Path $jarvisCmdPath -Value $jarvisCmd -Encoding ASCII
Write-Ok "Created $jarvisCmdPath"

# --- Step 5: Add to PATH ---
$userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$JARVIS_BIN*") {
    Write-Step "Adding $JARVIS_BIN to PATH..."
    [System.Environment]::SetEnvironmentVariable(
        "Path",
        "$userPath;$JARVIS_BIN",
        "User"
    )
    $env:Path = "$env:Path;$JARVIS_BIN"
    Write-Ok "Added to PATH (restart terminal for full effect)"
} else {
    Write-Ok "Already in PATH"
}

# --- Step 6: Verify ---
Write-Step "Verifying installation..."
try {
    Push-Location $JARVIS_DIR
    $version = & uv run python -c "from jarvis import __version__; print(__version__)" 2>&1
    Pop-Location
    Write-Ok "JARVIS v$version installed successfully!"
} catch {
    Write-Warn "Verification failed, but installation may still work"
}

# --- Done ---
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  JARVIS installed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Quick start:" -ForegroundColor White
Write-Host "    jarvis setup     " -ForegroundColor Cyan -NoNewline
Write-Host "  First-time configuration"
Write-Host "    jarvis           " -ForegroundColor Cyan -NoNewline
Write-Host "  Launch dashboard"
Write-Host "    jarvis --headless" -ForegroundColor Cyan -NoNewline
Write-Host "  Voice-only mode"
Write-Host ""
Write-Host "  Restart your terminal, then run: " -NoNewline
Write-Host "jarvis setup" -ForegroundColor Cyan
Write-Host ""
