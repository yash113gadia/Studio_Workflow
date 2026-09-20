# Start ComfyUI Service
$ErrorActionPreference = "Stop"
$root = "C:\Users\nikhi\Preeti_Studio"
Set-Location $root

$gitPath = "C:\Users\nikhi\AppData\Local\Microsoft\WinGet\Packages\Git.MinGit_Microsoft.Winget.Source_8wekyb3d8bbwe\cmd\git.exe"
$env:GIT_PYTHON_GIT_EXECUTABLE = $gitPath
if (Test-Path "C:\Users\nikhi\AppData\Local\Microsoft\WinGet\Packages\Git.MinGit_Microsoft.Winget.Source_8wekyb3d8bbwe\cmd") {
    $env:Path = "C:\Users\nikhi\AppData\Local\Microsoft\WinGet\Packages\Git.MinGit_Microsoft.Winget.Source_8wekyb3d8bbwe\cmd;$env:Path"
}

$python = "$root\environments\comfy_env\Scripts\python.exe"
$comfyMain = "$root\services\comfyui\ComfyUI\main.py"
$logsDir = "$root\logs"
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }

$pidFile = "$logsDir\comfyui.pid"
$logFile = "$logsDir\comfyui.log"
$errFile = "$logsDir\comfyui_err.log"

if (Test-Path $pidFile) {
    $existingPid = Get-Content $pidFile
    if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) {
        Write-Host "ComfyUI is already running with PID $existingPid"
        exit 0
    } else {
        Remove-Item $pidFile -Force
    }
}

Write-Host "Starting ComfyUI on 127.0.0.1:8188..."
# Launch ComfyUI
$process = Start-Process -WindowStyle Hidden -FilePath $python -ArgumentList $comfyMain, "--listen", "127.0.0.1", "--port", "8188", "--extra-model-paths-config", "$root\services\comfyui\extra_model_paths.yaml" -WorkingDirectory "$root\services\comfyui\ComfyUI" -RedirectStandardOutput $logFile -RedirectStandardError $errFile -PassThru

$process.Id | Out-File -FilePath $pidFile -Encoding ascii
Write-Host "ComfyUI process launched with PID $($process.Id)."

# Poll for ready
$ready = $false
for ($i = 0; $i -lt 45; $i++) {
    Start-Sleep -Seconds 1
    try {
        $stats = Invoke-RestMethod -Uri "http://127.0.0.1:8188/system_stats" -Method Get -TimeoutSec 2
        if ($stats) {
            $ready = $true
            Write-Host "ComfyUI is ready! System stats verified."
            break
        }
    } catch {
        # continue waiting
    }
}

if (-not $ready) {
    Write-Warning "ComfyUI started, but /system_stats is not responding yet. Check $logFile and $errFile"
}
