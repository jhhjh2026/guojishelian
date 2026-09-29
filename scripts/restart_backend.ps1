[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$ErrorActionPreference = 'SilentlyContinue'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

Write-Host "Stopping Python processes on port 8000..."
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object {
    $proc = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "Killing PID $($proc.Id) - $($proc.ProcessName)"
        Stop-Process -Id $proc.Id -Force
    }
}

Start-Sleep -Seconds 2

Write-Host "Starting backend from: $projectRoot"
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "ERROR: .venv not found."
    exit 1
}

$proc = Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-m","backend.app.server" -NoNewWindow -PassThru
Write-Host "Backend starting... PID=$($proc.Id)"

$healthUrl = "http://127.0.0.1:8000/api/health"
$maxRetries = 60
$retryIntervalSec = 1
for ($i=1; $i -le $maxRetries; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) {
            Write-Host "Backend is ready: $healthUrl"
            Write-Host "Open frontend with: .\scripts\start_frontend.ps1 (if available)"
            exit 0
        }
    } catch {
        # not ready yet
    }
    Start-Sleep -Seconds $retryIntervalSec
}
Write-Host "Backend health check timed out after ${maxRetries}s."
exit 1
