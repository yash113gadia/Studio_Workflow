# Phase 2: Setup ComfyUI in isolated environment
# Called by scripts/setup_windows.ps1; can also be run on its own. Safe to re-run.
param(
    [string]$PythonHost = "",
    [ValidateSet("cu126", "cu130")]
    [string]$CudaIndex = "cu130"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# ComfyUI build and PyTorch version verified on the original RTX 3070 (docs/KNOWN_GOOD.md)
$comfyCommit = "3c80da7f87ee359b2d06f107cb3c0797079dfbbb"
$torchVersion = "2.14.0"

$comfyEnv = "$root\environments\comfy_env"
$comfyDir = "$root\services\comfyui\ComfyUI"

function Assert-ExitCode([string]$what) {
    if ($LASTEXITCODE -ne 0) { throw "$what failed (exit code $LASTEXITCODE)." }
}

if (-not $PythonHost) {
    $PythonHost = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
}
if (-not (Test-Path $PythonHost)) { throw "Python 3.11 not found at $PythonHost" }

if (-not (Test-Path "$comfyDir\main.py")) {
    Write-Host "Downloading ComfyUI (pinned build $($comfyCommit.Substring(0, 7)))..."
    $tempDir = "$root\temp\comfyui_download"
    if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    $zip = "$tempDir\ComfyUI.zip"
    Invoke-WebRequest -Uri "https://github.com/Comfy-Org/ComfyUI/archive/$comfyCommit.zip" -OutFile $zip -UseBasicParsing
    $tar = Get-Command tar.exe -ErrorAction SilentlyContinue
    if ($tar) {
        & $tar.Source -xf $zip -C $tempDir
        Assert-ExitCode "Extracting ComfyUI"
    } else {
        Expand-Archive -Path $zip -DestinationPath $tempDir -Force
    }
    if (Test-Path $comfyDir) { Remove-Item $comfyDir -Recurse -Force }
    Move-Item -Path "$tempDir\ComfyUI-$comfyCommit" -Destination $comfyDir
    Remove-Item $tempDir -Recurse -Force
}

Write-Host "Creating comfy_env virtual environment..."
if (-not (Test-Path "$comfyEnv\Scripts\python.exe")) {
    & $PythonHost -m venv $comfyEnv
    Assert-ExitCode "Creating comfy_env"
}

$comfyPython = "$comfyEnv\Scripts\python.exe"

Write-Host "Upgrading pip and installing build tools..."
& $comfyPython -m pip install --upgrade pip setuptools wheel
Assert-ExitCode "Upgrading pip"

Write-Host "Installing PyTorch $torchVersion with CUDA ($CudaIndex), about 3 GB..."
& $comfyPython -m pip install "torch==$torchVersion" torchvision torchaudio --index-url "https://download.pytorch.org/whl/$CudaIndex"
Assert-ExitCode "Installing PyTorch"

Write-Host "Installing ComfyUI requirements..."
# The constraint stops pip from swapping the CUDA build of torch for the CPU-only one on PyPI.
$constraints = "$root\temp\comfy_torch_constraint.txt"
New-Item -ItemType Directory -Path "$root\temp" -Force | Out-Null
Set-Content -Path $constraints -Value "torch==$torchVersion+$CudaIndex" -Encoding ascii
& $comfyPython -m pip install -r "$comfyDir\requirements.txt" -c $constraints --extra-index-url "https://download.pytorch.org/whl/$CudaIndex"
Assert-ExitCode "Installing ComfyUI requirements"

Write-Host "Checking that PyTorch can use the NVIDIA GPU..."
& $comfyPython -c "import sys, torch; ok = torch.cuda.is_available(); print('torch', torch.__version__, '| CUDA', torch.version.cuda, '| GPU', torch.cuda.get_device_name(0) if ok else 'NOT AVAILABLE'); sys.exit(0 if ok else 1)"
Assert-ExitCode "PyTorch GPU check"

Write-Host "Installing the Studio sidebar extension into ComfyUI..."
$extensionDir = "$comfyDir\custom_nodes\ComfyUI-AIStudio"
if (Test-Path $extensionDir) { Remove-Item $extensionDir -Recurse -Force }
Copy-Item -Path "$root\services\comfyui\ComfyUI-AIStudio" -Destination $extensionDir -Recurse

Write-Host "ComfyUI setup completed."
