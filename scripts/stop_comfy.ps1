# Stop ComfyUI Service Gracefully
$ErrorActionPreference = "Continue"
$root = "C:\Users\nikhi\Preeti_Studio"
$pidFile = "$root\logs\comfyui.pid"

if (-not (Test-Path $pidFile)) {
    Write-Host "ComfyUI PID file not found. Process not running."
    exit 0
}

$procId = Get-Content $pidFile
$proc = Get-Process -Id $procId -ErrorAction SilentlyContinue

if ($proc) {
    Write-Host "Stopping ComfyUI (PID $procId)..."
    Stop-Process -Id $procId -Force
    Write-Host "ComfyUI stopped."
} else {
    Write-Host "Process with PID $procId not found. Cleaning up PID file."
}

Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
