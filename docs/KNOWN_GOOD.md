# Known-Good Versions and Passed Profiles (KNOWN_GOOD.md)

This document pins exact known-good commits, SHAs, model hashes, Python versions, and benchmark results. Do not update working production components without logging and regression testing here.

---

## Environment Baselines

| Component | Target Version / Commit | Tested & Verified | Notes |
|---|---|---|---|
| **OS** | Windows 11 Home 10.0.26200 | Yes (Phase 0) | Host platform |
| **NVIDIA Driver** | 560+ / 610.60 | Yes (Phase 0) | Reported by nvidia-smi |
| **CUDA Runtime** | 12.x / 13.3 UMD | Yes (Phase 0) | Host driver layer |
| **Python** | 3.11.9 | Yes (Phase 1) | For Studio Core in `environments/studio_core_env` |
| **Git** | 2.55.0.windows.5 | Yes (Phase 0/1) | MinGit portable |
| **FFmpeg** | 9.0.1-essentials_build | Yes (Phase 0/1) | Gyan.FFmpeg Essentials |
| **Studio Core API** | v0.1.0 | Yes (Phase 1) | FastAPI + SQLite + WAL mode |
| **ComfyUI Core** | Pinned Git commit | Pending Phase 2 | Upstream baseline |
| **ComfyUI-AIStudio** | v0.1.0 | Pending Phase 3 | Studio UI extension |
| **FLUX.2 Klein 4B Distilled** | Official BFL / Comfy Org | Pending Phase 4 | Central model store |

---

## Passed Verification Profiles

- **Profile `phase-01-core-foundation`**:
  - Test Suite: `tests/test_phase_01_core.py` (6 passed in 0.80s).
  - Verified: Project CRUD, durable queue persistence in SQLite, process crash simulation & stale `RUNNING` recovery, global GPU mutex lease mutual exclusion (`GPU0_HEAVY`), `/api/v1/health` and `/api/v1/jobs` endpoints.
  - Startup / Shutdown scripts verified: `scripts/start_studio.ps1`, `scripts/stop_studio.ps1`.
