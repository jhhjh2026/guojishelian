[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

Write-Host "Project root: $projectRoot"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "ERROR: .venv not found. Create venv and install requirements first."
    exit 1
}

Write-Host "Starting backend server on http://127.0.0.1:8000 ..."
Write-Host "Press Ctrl+C to stop."
& ".\.venv\Scripts\python.exe" -m backend.app.server
