# Herald — run local voice pipeline (Phase 1, Windows)
# No server or WebSocket needed — uses mic + speaker directly via PyAudio.
# Usage:
#   .\scripts\local_test.ps1
#   .\scripts\local_test.ps1 -Mode talky -ContextFile "C:\path\to\session.json"

param(
    [ValidateSet("freeform", "talky", "family_interview")]
    [string]$Mode = "freeform",
    [string]$ContextFile = ""
)

$ErrorActionPreference = "Stop"
$HeraldRoot = Split-Path -Parent $PSScriptRoot
$VenvDir = Join-Path $HeraldRoot ".venv"

if (-not (Test-Path $VenvDir)) {
    Write-Error ".venv not found. Run: .\scripts\setup.ps1"
}

# Load .env if present
$EnvFile = Join-Path $HeraldRoot ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | Where-Object { $_ -match "^\s*[^#]" -and $_ -match "=" } | ForEach-Object {
        $parts = $_ -split "=", 2
        [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
    }
}

$ollamaUrl = [System.Environment]::GetEnvironmentVariable("OLLAMA_BASE_URL", "Process") ?? "http://localhost:11434"

# Check Ollama
try {
    $null = Invoke-RestMethod -Uri "$ollamaUrl/api/tags" -TimeoutSec 3
} catch {
    Write-Warning "Ollama not responding at $ollamaUrl"
    Write-Warning "Start it with: ollama serve"
    $reply = Read-Host "Continue anyway? [y/N]"
    if ($reply -notmatch "^[Yy]$") { exit 1 }
}

$python = Join-Path $VenvDir "Scripts\python.exe"

Write-Host "=== Herald local voice pipeline ===" -ForegroundColor Cyan
Write-Host "Mode: $Mode"
if ($ContextFile) { Write-Host "Context: $ContextFile" }
Write-Host ""

$args = @("--mode", $Mode)
if ($ContextFile) { $args += @("--context", $ContextFile) }

Set-Location $HeraldRoot
& $python -m server.local_pipeline @args
