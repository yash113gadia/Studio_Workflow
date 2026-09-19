# Machine Audit (Phase 0)
**Date:** 2026-09-19  
**Machine:** Windows 11 Laptop (NIKHIL-PC)  
**Audit Script:** `scripts/audit_machine.ps1`  
**Raw Results:** `scripts/audit_results.json`

---

## 1. Hardware & OS Verification

| Component | Target Spec in Plan | Measured Value on Machine | Match Status |
|---|---|---|---|
| **Operating System** | Windows 11 64-bit | Microsoft Windows 11 Home (Version 10.0.26200, 64-bit) | **MATCH** |
| **CPU** | AMD Ryzen 9 5900HX | AMD Ryzen 9 5900HX with Radeon Graphics (8 Cores, 16 Logical Processors) | **MATCH** |
| **GPU** | NVIDIA RTX 3070 Laptop 8GB | NVIDIA GeForce RTX 3070 Laptop GPU (8192 MiB VRAM) | **MATCH** |
| **Integrated GPU** | AMD Radeon Graphics | AMD Radeon(TM) Graphics (512 MB shared) | **MATCH** |
| **NVIDIA Driver** | Current driver | 32.0.16.1060 (Driver Version 610.60) | **MATCH** |
| **CUDA Runtime** | 12.x / 13.x | CUDA UMD Version 13.3 reported by nvidia-smi | **MATCH** |
| **System RAM** | 16 GB | 16,097,532 KB (~15.35 GiB total, ~3.9 GiB free at audit) | **MATCH** |
| **Storage / Disks** | ~300 GB free | Drive `C:\`: 268.85 GB Free / 665.47 GB Used (No `D:\` drive) | **MATCH** (Root will be `C:\Users\nikhi\Preeti_Studio`) |
| **Pagefile** | Active Windows pagefile | `C:\pagefile.sys` active, 13,312 MB allocated, 278 MB used | **MATCH** |

---

## 2. Ports Availability

| Port | Service | Status |
|---|---|---|
| **8000** | Studio Core (FastAPI sidecar) | **AVAILABLE** |
| **8188** | ComfyUI | **AVAILABLE** |
| **7860** | WanGP | **AVAILABLE** |
| **8080** | Alternate / VLM | **AVAILABLE** |

---

## 3. Toolchain & Prerequisites Status

| Tool | Status / Path | Notes |
|---|---|---|
| `winget` | Available (`v1.29.290`) | Standard Windows package manager |
| `git` | Installed (`2.55.0.windows.5`) | MinGit 64-bit |
| `python` | Installed (`3.11.9`) | CPython 3.11 64-bit |
| `ffmpeg` | Installed (`9.0.1-essentials_build`) | Gyan.FFmpeg Essentials build |
| Visual C++ Tools | Not found | Standard prebuilt wheels preferred |
| Existing ComfyUI/Wan | None found | Fresh installation directory |

---

## 4. Hardware Suitability & Operating Constraints

1. **Hardware Profile**: The machine matches the exact hardware baseline specified in the Master Plan:
   `RTX 3070 Laptop 8 GB, Ryzen 9 5900HX, 16 GB RAM, Windows 11`.
2. **Storage Safety Buffer**: `C:\` has ~268.85 GB free. The plan mandates keeping a minimum 80 GB free disk safety margin. Model downloads must be strictly staged (FLUX.2 Klein 4B distilled first).
3. **RAM & VRAM Management**: With 16 GB host RAM and 8 GB VRAM, the global GPU lease and strict sequential heavy process execution (one model runtime active at a time) are non-negotiable.
