#Requires -Version 5.1
<#
.SYNOPSIS
    JARVIS plug & play installer for Windows.

.DESCRIPTION
    Fully automated installer. Checks and installs ALL dependencies:
    - Git (via winget)
    - uv (Python package manager)
    - Python 3.12 (via uv)
    - JARVIS + all dependencies
    - Adds 'jarvis' command to PATH

    Zero prerequisites except PowerShell and internet.

.EXAMPLE
    irm https://raw.githubusercontent.com/MiguelAguiarDEV/jarvis/main/install.ps1 | iex
#>

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"  # Speed up Invoke-WebRequest

$JARVIS_DIR = "$env:USERPROFILE\.jarvis"
$JARVIS_BIN = "$env:USERPROFILE\.local\bin"
$REPO_URL = "https://github.com/MiguelAguiarDEV/jarvis.git"

# ============================================================
# Helpers
# ============================================================

function Write-Banner {
    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host "       JARVIS Installer" -ForegroundColor Cyan
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([string]$Num, [string]$Message)
    Write-Host ""
    Write-Host "  [$Num] " -ForegroundColor Cyan -NoNewline
    Write-Host $Message
}

function Write-Check {
    param([string]$Message)
    Write-Host "      Checking: " -ForegroundColor DarkGray -NoNewline
    Write-Host $Message -ForegroundColor DarkGray
}

function Write-Ok {
    param([string]$Message)
    Write-Host "      [OK] " -ForegroundColor Green -NoNewline
    Write-Host $Message
}

function Write-Installing {
    param([string]$Message)
    Write-Host "      Installing: " -ForegroundColor Yellow -NoNewline
    Write-Host $Message
}

function Write-Fail {
    param([string]$Message)
    Write-Host "      [FAIL] " -ForegroundColor Red -NoNewline
    Write-Host $Message
}

function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + `
                [System.Environment]::GetEnvironmentVariable("Path", "User")
}

function Test-Command {
    param([string]$Name)
    $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

# ============================================================
# Step 1: Git
# ============================================================

function Ensure-Git {
    Write-Step "1/6" "Git"
    
    if (Test-Command "git") {
        $v = & git --version 2>&1
        Write-Ok "Found: $v"
        return
    }

    Write-Installing "Git via winget..."
    
    if (Test-Command "winget") {
        try {
            & winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements 2>&1 | Out-Null
            Refresh-Path
            if (Test-Command "git") {
                Write-Ok "Git installed"
                return
            }
        } catch {}
    }

    # Fallback: direct download
    Write-Installing "Git via direct download..."
    $gitInstaller = "$env:TEMP\git-installer.exe"
    try {
        Invoke-WebRequest -Uri "https://github.com/git-for-windows/git/releases/latest/download/Git-2.47.1-64-bit.exe" `
            -OutFile $gitInstaller -UseBasicParsing
        Start-Process -FilePath $gitInstaller -ArgumentList "/VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS /COMPONENTS=`"`"" -Wait
        Remove-Item $gitInstaller -ErrorAction SilentlyContinue
        Refresh-Path
        
        # Git installs to Program Files, add to current session
        $gitPaths = @(
            "$env:ProgramFiles\Git\cmd",
            "${env:ProgramFiles(x86)}\Git\cmd"
        )
        foreach ($gp in $gitPaths) {
            if (Test-Path $gp) { $env:Path += ";$gp" }
        }
        
        if (Test-Command "git") {
            Write-Ok "Git installed"
            return
        }
    } catch {}

    Write-Fail "Could not install Git automatically."
    Write-Host "      Please install Git manually: https://git-scm.com/download/win" -ForegroundColor Yellow
    Write-Host "      Then re-run this installer." -ForegroundColor Yellow
    exit 1
}

# ============================================================
# Step 2: uv
# ============================================================

function Ensure-Uv {
    Write-Step "2/6" "uv (Python package manager)"
    
    if (Test-Command "uv") {
        $v = & uv --version 2>&1
        Write-Ok "Found: $v"
        return
    }

    Write-Installing "uv from astral.sh..."
    try {
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
        Refresh-Path
        
        # uv installs to ~/.local/bin or ~/.cargo/bin
        $uvPaths = @(
            "$env:USERPROFILE\.local\bin",
            "$env:USERPROFILE\.cargo\bin"
        )
        foreach ($up in $uvPaths) {
            if (Test-Path "$up\uv.exe") { $env:Path += ";$up" }
        }
        
        if (Test-Command "uv") {
            $v = & uv --version 2>&1
            Write-Ok "Installed: $v"
            return
        }
    } catch {}

    Write-Fail "Could not install uv."
    Write-Host "      Install manually: https://docs.astral.sh/uv/" -ForegroundColor Yellow
    exit 1
}

# ============================================================
# Step 3: Python (via uv)
# ============================================================

function Ensure-Python {
    Write-Step "3/6" "Python 3.12"
    
    # uv manages Python — just ensure 3.12 is available
    Write-Check "Python via uv..."
    try {
        $pythonList = & uv python list 2>&1 | Select-String "3\.12"
        if ($pythonList) {
            Write-Ok "Python 3.12 available via uv"
            return
        }
    } catch {}

    Write-Installing "Python 3.12 via uv..."
    try {
        & uv python install 3.12 2>&1 | Out-Null
        Write-Ok "Python 3.12 installed"
    } catch {
        Write-Fail "Could not install Python 3.12: $_"
        Write-Host "      Install manually: https://www.python.org/downloads/" -ForegroundColor Yellow
        exit 1
    }
}

# ============================================================
# Step 4: Clone/Update JARVIS
# ============================================================

function Ensure-Repo {
    Write-Step "4/6" "JARVIS repository"
    
    if (Test-Path "$JARVIS_DIR\.git") {
        Write-Check "Updating existing installation..."
        Push-Location $JARVIS_DIR
        try {
            & git pull --ff-only 2>&1 | Out-Null
            Write-Ok "Updated to latest version"
        } catch {
            Write-Ok "Already up to date"
        }
        Pop-Location
        return
    }

    if (Test-Path $JARVIS_DIR) {
        Remove-Item -Recurse -Force $JARVIS_DIR
    }

    Write-Installing "Cloning repository..."
    & git clone --depth 1 $REPO_URL $JARVIS_DIR 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to clone repository"
        exit 1
    }
    Write-Ok "Repository cloned to $JARVIS_DIR"
}

# ============================================================
# Step 5: Install dependencies
# ============================================================

function Install-Dependencies {
    Write-Step "5/6" "Dependencies"
    
    Push-Location $JARVIS_DIR
    
    # Try with audio first (PyAudio), fall back to without
    Write-Installing "Python packages (this may take a minute)..."
    try {
        & uv sync --extra dev --extra audio 2>&1 | Out-Null
        Write-Ok "All dependencies installed (including audio)"
    } catch {
        Write-Check "Retrying without PyAudio..."
        try {
            & uv sync --extra dev 2>&1 | Out-Null
            Write-Ok "Core dependencies installed"
            Write-Host "      Note: PyAudio not installed. Run 'jarvis setup' to configure audio." -ForegroundColor Yellow
        } catch {
            Write-Fail "Failed to install dependencies: $_"
            Pop-Location
            exit 1
        }
    }
    
    Pop-Location
}

# ============================================================
# Step 6: Create command + PATH
# ============================================================

function Install-Command {
    Write-Step "6/6" "Creating 'jarvis' command"
    
    # Create bin directory
    if (-not (Test-Path $JARVIS_BIN)) {
        New-Item -ItemType Directory -Path $JARVIS_BIN -Force | Out-Null
    }

    # Create jarvis.cmd wrapper
    $cmdContent = @"
@echo off
pushd "$JARVIS_DIR" >nul 2>&1
uv run python -m jarvis %*
popd >nul 2>&1
"@
    Set-Content -Path "$JARVIS_BIN\jarvis.cmd" -Value $cmdContent -Encoding ASCII
    Write-Ok "Created jarvis command"

    # Add to user PATH if not already there
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$JARVIS_BIN*") {
        [System.Environment]::SetEnvironmentVariable("Path", "$userPath;$JARVIS_BIN", "User")
        $env:Path += ";$JARVIS_BIN"
        Write-Ok "Added to PATH"
    } else {
        Write-Ok "Already in PATH"
    }
}

# ============================================================
# Verify
# ============================================================

function Test-Installation {
    Write-Host ""
    Write-Host "  Verifying..." -ForegroundColor DarkGray
    
    Push-Location $JARVIS_DIR
    try {
        $version = & uv run python -c "from jarvis import __version__; print(__version__)" 2>&1
        Write-Ok "JARVIS v$version ready"
        Pop-Location
        return $true
    } catch {
        Write-Fail "Verification failed: $_"
        Pop-Location
        return $false
    }
}

# ============================================================
# Main
# ============================================================

Write-Banner

Ensure-Git
Ensure-Uv
Ensure-Python
Ensure-Repo
Install-Dependencies
Install-Command

$ok = Test-Installation

Write-Host ""
if ($ok) {
    Write-Host "  ============================================" -ForegroundColor Green
    Write-Host "    JARVIS installed successfully!" -ForegroundColor Green
    Write-Host "  ============================================" -ForegroundColor Green
} else {
    Write-Host "  ============================================" -ForegroundColor Yellow
    Write-Host "    Installed with warnings (may still work)" -ForegroundColor Yellow
    Write-Host "  ============================================" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host ""
Write-Host "    1. " -NoNewline
Write-Host "Close and reopen this terminal" -ForegroundColor Yellow
Write-Host "    2. " -NoNewline
Write-Host "jarvis setup" -ForegroundColor Cyan -NoNewline
Write-Host "      Configure JARVIS (downloads models, sets up auth)"
Write-Host "    3. " -NoNewline
Write-Host "jarvis" -ForegroundColor Cyan -NoNewline
Write-Host "            Launch the dashboard"
Write-Host ""
