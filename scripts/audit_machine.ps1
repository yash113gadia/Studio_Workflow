# Phase 0: Read-Only Machine Audit Script
# Purpose: Collect hardware and software facts without altering system settings

$ErrorActionPreference = "Continue"

Write-Host "========================================="
Write-Host " AI STUDIO MACHINE AUDIT (Phase 0) "
Write-Host "========================================="

$audit = [ordered]@{}

# 1. Operating System
$os = Get-CimInstance Win32_OperatingSystem
$audit["OS_Caption"] = $os.Caption
$audit["OS_Version"] = $os.Version
$audit["OS_Build"] = $os.BuildNumber
$audit["OS_Architecture"] = $os.OSArchitecture
$audit["Total_Visible_Memory_KB"] = $os.TotalVisibleMemorySize
$audit["Free_Physical_Memory_KB"] = $os.FreePhysicalMemory

# 2. CPU
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$audit["CPU_Name"] = $cpu.Name
$audit["CPU_Cores"] = $cpu.NumberOfCores
$audit["CPU_LogicalProcessors"] = $cpu.NumberOfLogicalProcessors

# 3. GPU / Video Controllers
$gpus = Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, AdapterRAM
$audit["Video_Controllers"] = $gpus

# 4. NVIDIA-SMI / CUDA
try {
    $nvsmi = nvidia-smi 2>&1
    $audit["NVIDIA_SMI_Output"] = ($nvsmi -join "`n")
} catch {
    $audit["NVIDIA_SMI_Output"] = "nvidia-smi not available or failed"
}

# 5. Disks & Free Space
$disks = Get-PSDrive -PSProvider FileSystem | Select-Object Name, Root, @{Name="FreeGB";Expression={[math]::Round($_.Free / 1GB, 2)}}, @{Name="UsedGB";Expression={[math]::Round($_.Used / 1GB, 2)}}
$audit["Disks"] = $disks

# 6. Pagefile Status
$pagefile = Get-CimInstance Win32_PageFileSetting -ErrorAction SilentlyContinue
if (-not $pagefile) {
    $pagefile = Get-CimInstance Win32_PageFileUsage -ErrorAction SilentlyContinue
}
$audit["Pagefile"] = $pagefile

# 7. Python, Git, FFmpeg, Package Managers
$tools = @("python", "py", "git", "git-lfs", "ffmpeg", "ffprobe", "uv", "pip", "conda", "micromamba", "node", "npm", "pnpm", "winget")
$toolAudit = [ordered]@{}
foreach ($t in $tools) {
    $cmd = Get-Command $t -ErrorAction SilentlyContinue
    if ($cmd) {
        $ver = ""
        try {
            if ($t -eq "python" -or $t -eq "py") { $ver = & $t --version 2>&1 }
            elseif ($t -eq "git") { $ver = & $t --version 2>&1 }
            elseif ($t -eq "git-lfs") { $ver = & $t version 2>&1 }
            elseif ($t -eq "ffmpeg") { $ver = (& $t -version 2>&1 | Select-Object -First 1) }
            elseif ($t -eq "node") { $ver = & $t --version 2>&1 }
            elseif ($t -eq "npm") { $ver = & $t --version 2>&1 }
            elseif ($t -eq "winget") { $ver = & $t --version 2>&1 }
            elseif ($t -eq "uv") { $ver = & $t --version 2>&1 }
            else { $ver = "Found" }
        } catch {
            $ver = "Error checking version"
        }
        $toolAudit[$t] = @{ Path = $cmd.Source; Version = "$ver".Trim() }
    } else {
        $toolAudit[$t] = "NOT INSTALLED / NOT IN PATH"
    }
}
$audit["Tools"] = $toolAudit

# 8. Visual C++ Build Tools Detection
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (Test-Path $vswhere) {
    $audit["VS_Build_Tools"] = (& $vswhere -latest -property installationPath 2>&1)
} else {
    $audit["VS_Build_Tools"] = "vswhere not found"
}

# 9. Ports in use (Studio Core proposed: 8000, ComfyUI: 8188, WanGP: 7860)
$portsToCheck = @(8000, 8188, 7860, 8080)
$portAudit = [ordered]@{}
foreach ($p in $portsToCheck) {
    $inUse = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue
    if ($inUse) {
        $portAudit["$p"] = "IN USE by PID $(($inUse | Select-Object -First 1).OwningProcess)"
    } else {
        $portAudit["$p"] = "AVAILABLE"
    }
}
$audit["Port_Status"] = $portAudit

# 10. Existing installations or model caches
$existingComfy = Get-ChildItem -Path "C:\Users\nikhi" -Directory -Filter "*ComfyUI*" -Depth 2 -ErrorAction SilentlyContinue | Select-Object FullName
$existingWan = Get-ChildItem -Path "C:\Users\nikhi" -Directory -Filter "*Wan*" -Depth 2 -ErrorAction SilentlyContinue | Select-Object FullName
$existingModels = Get-ChildItem -Path "C:\Users\nikhi\.cache\huggingface", "C:\Users\nikhi\.cache" -Directory -ErrorAction SilentlyContinue | Select-Object FullName
$audit["Existing_ComfyUI"] = $existingComfy
$audit["Existing_Wan"] = $existingWan
$audit["Existing_Caches"] = $existingModels

$audit | ConvertTo-Json -Depth 5 | Out-File -FilePath "scripts/audit_results.json" -Encoding utf8
Write-Host "Audit completed. Results saved to scripts/audit_results.json"
