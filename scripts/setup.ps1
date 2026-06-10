# Herald — Windows setup script
# Run once in an elevated PowerShell terminal.
# Prerequisites: Python 3.11+, Git, winget (comes with Windows 11)
#
# Usage:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\scripts\setup.ps1

$ErrorActionPreference = "Stop"
$HeraldRoot = Split-Path -Parent $PSScriptRoot

Write-Host "=== Herald setup (Windows) ===" -ForegroundColor Cyan
Write-Host "Root: $HeraldRoot"

# ── 1. Ollama ─────────────────────────────────────────────────────────────────
Write-Host "`n→ Checking Ollama..." -ForegroundColor Yellow
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "  Installing Ollama via winget..."
    winget install Ollama.Ollama --silent
    # Reload PATH
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH", "User")
}
Write-Host "  Pulling llama3.3 (this takes a while on first run)..."
ollama pull llama3.3

# ── 2. espeak-ng (required by Kokoro TTS) ────────────────────────────────────
Write-Host "`n→ Checking espeak-ng..." -ForegroundColor Yellow
if (-not (Get-Command espeak-ng -ErrorAction SilentlyContinue)) {
    Write-Host "  Installing espeak-ng via winget..."
    winget install eSpeak-NG.eSpeak-NG --silent 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "  winget install failed. Download manually from:"
        Write-Warning "  https://github.com/espeak-ng/espeak-ng/releases"
        Write-Warning "  Install, then re-run this script."
    }
}

# ── 3. Python venv ────────────────────────────────────────────────────────────
Write-Host "`n→ Setting up Python venv..." -ForegroundColor Yellow
$VenvDir = Join-Path $HeraldRoot ".venv"
if (-not (Test-Path $VenvDir)) {
    python -m venv $VenvDir
}

$pip = Join-Path $VenvDir "Scripts\pip.exe"
& $pip install --upgrade pip
# Server dependencies
& $pip install -r (Join-Path $HeraldRoot "server\requirements.txt")
# Pipecat extras including local audio (PyAudio)
# Note: PyAudio on Windows may need Microsoft C++ Build Tools if no pre-built wheel exists.
# If pip install fails: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
& $pip install "pipecat-ai[silero,kokoro,ollama,whisper,local]"

# ── 4. .env check ─────────────────────────────────────────────────────────────
Write-Host "`n→ Checking .env..." -ForegroundColor Yellow
$EnvFile = Join-Path $HeraldRoot ".env"
$EnvExample = Join-Path $HeraldRoot ".env.example"
if (-not (Test-Path $EnvFile)) {
    Copy-Item $EnvExample $EnvFile
    Write-Host "  Created .env from .env.example"
    Write-Host "  IMPORTANT: Set HERALD_AUTH_TOKEN in .env before running the server." -ForegroundColor Red
    Write-Host "  Generate: python -c `"import secrets; print(secrets.token_hex(32))`""
} else {
    Write-Host "  .env already exists — skipping"
}

Write-Host "`n=== Setup complete ===" -ForegroundColor Green
Write-Host "Next: .\scripts\dev.ps1"
