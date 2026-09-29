[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

Write-Host "Project root: $projectRoot"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "ERROR: .venv not found. Create venv and install requirements first."
    exit 1
}

# Check ports
$port8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
$port5173 = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
if ($port8000) { Write-Host "Warning: port 8000 already in use. Run .\scripts\restart_backend.ps1 if needed." }
if ($port5173) { Write-Host "Warning: port 5173 already in use. Stop existing Vite or change port." }

Write-Host "Starting backend (FastAPI) on http://127.0.0.1:8000 ..."
$backend = Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-m","backend.app.server" -NoNewWindow -PassThru

Write-Host "Starting frontend (Vite) on http://localhost:5173 ..."
$frontend = Start-Process -FilePath "npm" -ArgumentList "run","dev","--","--host" -Wait -NoNewWindow -PassThru -WorkingDirectory (Join-Path $projectRoot "frontend")

Write-Host "Frontend exited with code $($frontend.ExitCode)"
