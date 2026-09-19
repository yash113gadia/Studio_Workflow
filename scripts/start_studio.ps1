# Start Preeti Studio Core Service
param(
    [switch]$Background = $true
)

$ErrorActionPreference = "Stop"
$root = "C:\Users\nikhi\Preeti_Studio"
Set-Location $root

$python = "$root\environments\studio_core_env\Scripts\python.exe"
$logsDir = "$root\logs"
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }

$pidFile = "$logsDir\studio_core.pid"
$logFile = "$logsDir\studio_core.log"

# Check if already running
if (Test-Path $pidFile) {
    $existingPid = Get-Content $pidFile
    if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) {
        Write-Host "Studio Core is already running with PID $existingPid"
        exit 0
    } else {
        Remove-Item $pidFile -Force
    }
}

Write-Host "Starting Studio Core on 127.0.0.1:8000..."
$serverScript = "$root\scripts\run_server.py"
$process = Start-Process -FilePath $python -ArgumentList $serverScript -WorkingDirectory $root -RedirectStandardOutput $logFile -RedirectStandardError "$logsDir\studio_core_err.log" -PassThru

$process.Id | Out-File -FilePath $pidFile -Encoding ascii
Write-Host "Studio Core started successfully with PID $($process.Id)."

# Health probe check
Start-Sleep -Seconds 2
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -Method Get
    Write-Host "Studio Core Health Check: $($health.status) (Free disk: $($health.free_disk_gb) GB)"
} catch {
    Write-Warning "Studio Core is starting up or health probe had an issue. Check $logFile"
}
