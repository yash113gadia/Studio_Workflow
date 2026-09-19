# Known-Good Versions and Passed Profiles (KNOWN_GOOD.md)

This document pins exact known-good commits, SHAs, model hashes, Python versions, and benchmark results. Do not update working production components without logging and regression testing here.

---

## Environment Baselines

| Component | Target Version / Commit | Tested & Verified | Notes |
|---|---|---|---|
| **OS** | Windows 11 Home 10.0.26200 | Yes (Phase 0) | Host platform |
| **NVIDIA Driver** | 560+ / 610.60 | Yes (Phase 0) | Reported by nvidia-smi |
| **CUDA Runtime** | 12.x / 13.3 UMD | Yes (Phase 0) | Host driver layer |
| **Python** | 3.11.x | Pending Phase 1 | For Studio Core |
| **Git** | Current stable | Pending Phase 1 | Version control |
| **FFmpeg** | Current stable | Pending Phase 1 | Deterministic assembly |
| **ComfyUI Core** | Pinned Git commit | Pending Phase 2 | Upstream baseline |
| **ComfyUI-AIStudio** | v0.1.0 | Pending Phase 3 | Studio UI extension |
| **FLUX.2 Klein 4B Distilled** | Official BFL / Comfy Org | Pending Phase 4 | Central model store |

---

## Passed Verification Profiles

*(Populated after each phase acceptance test)*
