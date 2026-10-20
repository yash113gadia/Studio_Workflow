# One-time setup of Preeti Studio on a new Windows PC with an NVIDIA GPU.
# Started by Setup_Preeti_Studio.bat. Safe to re-run: finished steps are skipped
# and model downloads resume where they stopped.
param(
    [switch]$SkipModels,
    [switch]$SkipSmokeTest
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$logsDir = "$root\logs"
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
Start-Transcript -Path "$logsDir\setup.log" -Append | Out-Null

$coreEnv = "$root\environments\studio_core_env"
$corePython = "$coreEnv\Scripts\python.exe"
$freshInstall = -not (Test-Path $corePython)
$totalSteps = 8

function Step([int]$n, [string]$message) {
    Write-Host ""
    Write-Host "[$n/$totalSteps] $message" -ForegroundColor Cyan
}

function Stop-Setup([string]$message) {
    Write-Host ""
    Write-Host "SETUP STOPPED: $message" -ForegroundColor Red
    Write-Host "Fix the problem above, then double-click Setup_Preeti_Studio.bat again. Finished steps are skipped." -ForegroundColor Yellow
    Write-Host "Full log: $logsDir\setup.log"
    Stop-Transcript | Out-Null
    exit 1
}

function Assert-ExitCode([string]$what) {
    if ($LASTEXITCODE -ne 0) { Stop-Setup "$what failed (exit code $LASTEXITCODE)." }
}

function Find-Python311 {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:ProgramFiles\Python311\python.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try {
            $found = & py -3.11 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $found -and (Test-Path $found.Trim())) { return $found.Trim() }
        } catch { }
    }
    return $null
}

function Find-FFmpeg {
    $onPath = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    $local = Get-ChildItem -Path "$root\tools\ffmpeg\*\bin\ffmpeg.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($local) { return $local.FullName }
    $winget = Get-ChildItem -Path "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin\ffmpeg.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($winget) { return $winget.FullName }
    return $null
}

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "        PREETI STUDIO - ONE-TIME SETUP FOR THIS PC" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "Install folder: $root"
Write-Host "This downloads about 30 GB and can take an hour or more. Keep the laptop plugged in."

# The repository carries the original PC's database (its test projects, queued jobs and file paths).
# A new PC starts with an empty one, created on first start; the old file is kept as a backup, never deleted.
# This runs before anything is installed so a setup that stops midway still resets it on the next run.
$db = "$root\database\studio.db"
$freshMarker = "$root\database\.fresh_for_this_pc"
if ($freshInstall -and -not (Test-Path $freshMarker)) {
    if (Test-Path $db) {
        $backup = "$root\database\studio_from_original_pc.db.bak"
        Move-Item -Path $db -Destination $backup -Force
        Write-Host "Moved the original PC's database to $backup"
        $git = Get-Command git -ErrorAction SilentlyContinue
        if ($git -and (Test-Path "$root\.git")) {
            # Keep git from treating this PC's own database as a change to commit.
            & $git.Source -C $root update-index --skip-worktree database/studio.db
        }
    }
    Set-Content -Path $freshMarker -Value "This PC uses its own studio.db." -Encoding ascii
}

# ---------------------------------------------------------------------------
Step 1 "Checking this PC (GPU, driver, memory, disk)"

if ($root.Length -gt 60) {
    Write-Warning "The install folder path is long ($($root.Length) characters). If setup fails with 'path too long', move the folder to C:\Preeti_Studio and run setup again."
}

$nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if (-not $nvidiaSmi) {
    Stop-Setup "No NVIDIA driver found (nvidia-smi is missing). Install the latest NVIDIA driver for this GPU (Alienware Command Center / Dell SupportAssist, or nvidia.com/drivers), restart, and run setup again."
}
$gpuLine = (& $nvidiaSmi.Source --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits | Select-Object -First 1)
if (-not $gpuLine) { Stop-Setup "nvidia-smi did not report a GPU. Update the NVIDIA driver and restart." }
$gpuParts = $gpuLine.Split(",") | ForEach-Object { $_.Trim() }
$gpuName = $gpuParts[0]
$vramMb = 0.0
if (-not [double]::TryParse($gpuParts[1], [ref]$vramMb)) { $vramMb = 0.0 }
$vramGb = [math]::Round($vramMb / 1024, 1)
$driver = $gpuParts[2]
$driverMajor = 0
if (-not [int]::TryParse($driver.Split(".")[0], [ref]$driverMajor)) {
    Stop-Setup "Could not read the NVIDIA driver version from '$gpuLine'."
}
Write-Host "GPU:    $gpuName ($vramGb GB VRAM), driver $driver"

$ramGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
Write-Host "Memory: $ramGb GB"

$drive = Get-PSDrive -Name $root.Substring(0, 1)
$freeGb = [math]::Round($drive.Free / 1GB, 1)
Write-Host "Disk:   $freeGb GB free on $($root.Substring(0, 2))"

# PyTorch cu130 needs driver 580+. Older drivers get the cu126 build that ran on the original RTX 3070,
# except RTX 50-series (Blackwell), which cu126 does not support.
if ($driverMajor -ge 580) {
    $cudaIndex = "cu130"
} elseif ($gpuName -match "RTX 50\d\d") {
    Stop-Setup "$gpuName needs NVIDIA driver 580 or newer (installed: $driver). Update the driver, restart, and run setup again."
} elseif ($driverMajor -ge 528) {
    $cudaIndex = "cu126"
    Write-Warning "NVIDIA driver $driver is old. Setup will use the CUDA 12.6 build; updating the driver to 580+ is recommended."
} else {
    Stop-Setup "NVIDIA driver $driver is too old for PyTorch. Update the driver, restart, and run setup again."
}
Write-Host "PyTorch build: $cudaIndex"

if ($vramGb -lt 7.5) {
    Write-Warning "This GPU has $vramGb GB VRAM. The studio was tuned on 8 GB; expect slower renders and use cinematic mode if real-motion renders fail."
}
if ($ramGb -lt 15) {
    Write-Warning "This PC has $ramGb GB RAM. The studio was tuned on 16 GB; close other apps while rendering."
}
if ($freeGb -lt 15) {
    Stop-Setup "Only $freeGb GB free on this drive. Setup needs about 40 GB. Free up space and run setup again."
}

# ---------------------------------------------------------------------------
Step 2 "Python 3.11"

$python = Find-Python311
if (-not $python) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Installing Python 3.11 with winget..."
        & winget install -e --id Python.Python.3.11 --scope user --silent --accept-package-agreements --accept-source-agreements
        $python = Find-Python311
    }
    if (-not $python) {
        Write-Host "Downloading the Python 3.11.9 installer from python.org..."
        $installer = "$env:TEMP\python-3.11.9-amd64.exe"
        Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" -OutFile $installer -UseBasicParsing
        # No py launcher: it installs for all users and would need an admin prompt.
        Start-Process -FilePath $installer -ArgumentList "/quiet InstallAllUsers=0 PrependPath=0 Include_test=0 Include_launcher=0" -Wait
        $python = Find-Python311
    }
    if (-not $python) { Stop-Setup "Could not install Python 3.11. Install it from python.org (64-bit, 3.11.x) and run setup again." }
}
& $python --version
Assert-ExitCode "Python check"
Write-Host "Using $python"

# ---------------------------------------------------------------------------
Step 3 "FFmpeg"

$ffmpeg = Find-FFmpeg
if (-not $ffmpeg) {
    Write-Host "Downloading FFmpeg (about 110 MB) into tools\ffmpeg..."
    $toolsDir = "$root\tools\ffmpeg"
    New-Item -ItemType Directory -Path $toolsDir -Force | Out-Null
    $zip = "$toolsDir\ffmpeg-release-essentials.zip"
    try {
        Invoke-WebRequest -Uri "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $zip -UseBasicParsing
        Expand-Archive -Path $zip -DestinationPath $toolsDir -Force
        Remove-Item $zip -Force
    } catch {
        Write-Warning "FFmpeg download failed ($($_.Exception.Message)). Trying winget..."
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            & winget install -e --id Gyan.FFmpeg.Essentials --silent --accept-package-agreements --accept-source-agreements
        }
    }
    $ffmpeg = Find-FFmpeg
    if (-not $ffmpeg) { Stop-Setup "Could not install FFmpeg." }
}
Write-Host "Using $ffmpeg"

# ---------------------------------------------------------------------------
Step 4 "Studio Core Python environment"

if (-not (Test-Path $corePython)) {
    & $python -m venv $coreEnv
    Assert-ExitCode "Creating studio_core_env"
}
& $corePython -m pip install --upgrade pip
Assert-ExitCode "Upgrading pip"
& $corePython -m pip install -r "$root\requirements.txt"
Assert-ExitCode "Installing Studio Core requirements"

# ---------------------------------------------------------------------------
Step 5 "ComfyUI engine and PyTorch for $gpuName"

try {
    & "$PSScriptRoot\setup_comfyui.ps1" -PythonHost $python -CudaIndex $cudaIndex
} catch {
    Stop-Setup "ComfyUI setup failed: $($_.Exception.Message)"
}

# ---------------------------------------------------------------------------
Step 6 "AI models (FLUX.2 Klein, LTX-Video, DINOv2; about 24 GB)"

if ($SkipModels) {
    Write-Host "Skipped (-SkipModels)."
} else {
    & $corePython "$PSScriptRoot\download_core_models.py"
    Assert-ExitCode "Model download"
}

# ---------------------------------------------------------------------------
Step 7 "Desktop shortcut"

$desktop = [Environment]::GetFolderPath("Desktop")
if ($desktop) {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut("$desktop\Preeti Studio.lnk")
    $shortcut.TargetPath = "$root\Launch_Preeti_Studio.bat"
    $shortcut.WorkingDirectory = $root
    $shortcut.Save()
    Write-Host "Desktop shortcut created: Preeti Studio"
}

# ---------------------------------------------------------------------------
Step 8 "Start the studio and run a real test render"

try {
    & "$PSScriptRoot\start_comfy.ps1"
    & "$PSScriptRoot\start_studio.ps1"
} catch {
    Stop-Setup "Could not start the studio: $($_.Exception.Message). See the logs folder."
}

if ($SkipSmokeTest -or $SkipModels) {
    Write-Host "Smoke test skipped."
} else {
    Write-Host "Rendering a test image, voice line and 2-second video. The first render loads the models and can take several minutes..."
    Push-Location $root
    & $corePython "$PSScriptRoot\smoke_test.py"
    $smokeExit = $LASTEXITCODE
    Pop-Location
    if ($smokeExit -ne 0) {
        Stop-Setup "The test render failed. The studio is installed, but check logs\comfyui_err.log and logs\studio_core_err.log."
    }
}

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Green
Write-Host "  SETUP COMPLETE" -ForegroundColor Green
Write-Host "  Open the studio any time with the 'Preeti Studio' icon on the desktop" -ForegroundColor Green
Write-Host "  (or Launch_Preeti_Studio.bat). It runs at http://127.0.0.1:8000/" -ForegroundColor Green
Write-Host "=======================================================" -ForegroundColor Green
Start-Process "http://127.0.0.1:8000/"
Stop-Transcript | Out-Null
exit 0
