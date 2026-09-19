# Phase 2: Setup ComfyUI in isolated environment
$ErrorActionPreference = "Stop"
$root = "C:\Users\nikhi\Preeti_Studio"
Set-Location $root

$pythonHost = "C:\Users\nikhi\AppData\Local\Programs\Python\Python311\python.exe"
$comfyEnv = "$root\environments\comfy_env"
$comfyDir = "$root\services\comfyui\ComfyUI"

Write-Host "Creating comfy_env virtual environment..."
if (-not (Test-Path "$comfyEnv\Scripts\python.exe")) {
    & $pythonHost -m venv $comfyEnv
}

$comfyPython = "$comfyEnv\Scripts\python.exe"
$comfyPip = "$comfyEnv\Scripts\pip.exe"

Write-Host "Upgrading pip and installing build tools..."
& $comfyPython -m pip install --upgrade pip setuptools wheel

Write-Host "Installing PyTorch with CUDA 12.6 support..."
& $comfyPip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126

Write-Host "Installing ComfyUI requirements..."
& $comfyPip install -r "$comfyDir\requirements.txt"

# Link extra_model_paths.yaml into ComfyUI
$extraModelsSource = "$root\services\comfyui\extra_model_paths.yaml"
$extraModelsTarget = "$comfyDir\extra_model_paths.yaml"
Copy-Item -Path $extraModelsSource -Destination $extraModelsTarget -Force

Write-Host "Installing ComfyUI-Manager..."
$managerDir = "$comfyDir\custom_nodes\ComfyUI-Manager"
if (-not (Test-Path $managerDir)) {
    & "C:\Users\nikhi\AppData\Local\Microsoft\WinGet\Packages\Git.MinGit_Microsoft.Winget.Source_8wekyb3d8bbwe\cmd\git.exe" clone https://github.com/ltdrdata/ComfyUI-Manager.git $managerDir
}

Write-Host "ComfyUI setup completed."
