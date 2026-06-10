# Herald — start local dev server (Windows)
# Usage: .\scripts\dev.ps1
# Prerequisites: .\scripts\setup.ps1 has been run

$ErrorActionPreference = "Stop"
$HeraldRoot = Split-Path -Parent $PSScriptRoot
$VenvDir = Join-Path $HeraldRoot ".venv"
$EnvFile = Join-Path $HeraldRoot ".env"

if (-not (Test-Path $VenvDir)) {
    Write-Error ".venv not found. Run: .\scripts\setup.ps1"
}
if (-not (Test-Path $EnvFile)) {
    Write-Error ".env not found. Copy .env.example to .env and set HERALD_AUTH_TOKEN."
}

# Load .env
Get-Content $EnvFile | Where-Object { $_ -match "^\s*[^#]" -and $_ -match "=" } | ForEach-Object {
    $parts = $_ -split "=", 2
    [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
}

$token = [System.Environment]::GetEnvironmentVariable("HERALD_AUTH_TOKEN", "Process")
if (-not $token) {
    Write-Error "HERALD_AUTH_TOKEN is not set in .env`nGenerate: python -c `"import secrets; print(secrets.token_hex(32))`""
}

# Start Ollama if not running
$ollamaProc = Get-Process ollama -ErrorAction SilentlyContinue
if (-not $ollamaProc) {
    Write-Host "→ Starting Ollama..." -ForegroundColor Yellow
    Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 2
}

$env_name = [System.Environment]::GetEnvironmentVariable("HERALD_ENV", "Process")
$llm_model = [System.Environment]::GetEnvironmentVariable("HERALD_LOCAL_LLM_MODEL", "Process")

Write-Host "→ Starting Herald server..." -ForegroundColor Cyan
Write-Host "  Mode:  $($env_name ?? 'development')"
Write-Host "  LLM:   $($llm_model ?? 'llama3.3') (local Ollama)"
Write-Host ""

$uvicorn = Join-Path $VenvDir "Scripts\uvicorn.exe"
& $uvicorn server.main:app `
    --host 0.0.0.0 `
    --port 8765 `
    --reload `
    --log-level info `
    --app-dir $HeraldRoot
