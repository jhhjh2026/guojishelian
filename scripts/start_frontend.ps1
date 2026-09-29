[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

if (-not (Test-Path "frontend\package.json")) {
    Write-Host "ERROR: frontend/package.json not found."
    exit 1
}

$port5173 = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
if ($port5173) {
    Write-Host "Warning: frontend port 5173 already in use. Stop existing Vite or change port."
}

Write-Host "Starting frontend (Vite) on http://localhost:5173 ..."
Set-Location (Join-Path $projectRoot "frontend")
npm run dev -- --host
