# Stop Preeti Studio Core Service Gracefully

$ErrorActionPreference = "Continue"
$root = "C:\Users\nikhi\Preeti_Studio"
$pidFile = "$root\logs\studio_core.pid"

if (-not (Test-Path $pidFile)) {
    Write-Host "Studio Core PID file not found. Service does not appear to be running."
    exit 0
}

$procId = Get-Content $pidFile
$proc = Get-Process -Id $procId -ErrorAction SilentlyContinue

if ($proc) {
    Write-Host "Stopping Studio Core (PID $procId)..."
    Stop-Process -Id $procId -Force
    Write-Host "Studio Core stopped."
} else {
    Write-Host "Process with PID $procId not found. Cleaning up PID file."
}

Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
