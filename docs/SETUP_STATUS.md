# Setup Status

**Current Date:** 2026-09-19  
**Current Phase:** Phase 0 Completed, Transitioning to Phase 1  
**Project Root:** `C:\Users\nikhi\Preeti_Studio`

---

## Phase Summary Table

| Phase | Description | Status | Verification / Notes |
|---|---|---|---|
| **Phase 0** | Read-Only Machine Audit | **PASSED** | Hardware exact match: Ryzen 9 5900HX, RTX 3070 8GB, 16GB RAM, Windows 11. See `docs/MACHINE_AUDIT.md`. |
| **Phase 1** | Repository, Docs, Configs, DB & Durable Queue | **PASSED** | Scaffolding complete, Python 3.11 venv, FastAPI Studio Core, SQLite DB, durable queue, GPU lease, 6 automated acceptance tests passed (`tests/test_phase_01_core.py`). |
| **Phase 2** | Clean ComfyUI Baseline & API Adapter | **PASSED** | Isolated `comfy_env` (PyTorch 2.14.0+cu126, CUDA 12.6, RTX 3070 detected, 958 nodes loaded, Manager v3.42). Acceptance test `scripts/test_comfy_api.py` passed and verified output image generation without manual clicking. |
| **Phase 3** | ComfyUI AI Studio UI Extension Shell | **PASSED** | `ComfyUI-AIStudio` frontend extension loaded by ComfyUI, serves `studio.js` and `studio.css`, connects to Studio Core over localhost, project creation, dummy job queuing, and restart persistence verified by automated test suite (`tests/test_phase_03_ui_extension.py`). |
| **Phase 4** | Workflow Registry & FLUX.2 Klein Asset Factory | **PASSED** | Official upstream templates registered & bit-verified. Downloaded & SHA256-verified FLUX.2 Klein FP8 (4.07 GB), Qwen 3.4B (8.04 GB), and FLUX2 VAE (336 MB). ComfyUI API end-to-end image generation verified (~15s on RTX 3070). Character Asset Factory (casting session, approval as immutable `CHAR_*_V001`, 5 canonical angle derivation) and UI controls implemented and verified via automated test suite (`tests/test_phase_04_flux_factory.py` 6/6 passed, 15/15 all project tests passed). |
| **Phase 5** | Qwen-Image-Edit-2511 Specialist | **IN PROGRESS** | Untouched official template registered. 6 specialist workflows generated in `workflows/api_format/`. Specialist editor service (`app/core/specialist_editor.py`), REST API (`/api/v1/editor`), ComfyUI sidebar UI controls (`studio.js`), and acceptance tests (`tests/test_phase_05_qwen_editor.py` 3/3 passed, 18/18 project tests passed). Model weights downloading (`qwen_image_vae` verified, Lightning LoRA in progress, FP8 text encoder + INT8 ConvRot diffusion model queued). |
| **Phase 6** | Memory, Canon & Continuity DB | **PASSED** | Relational schema migration v2 applied (characters, wardrobe, locations, location states, props, prop states, voices, relationships, episodes, scenes, shots, scene character/location states, continuity events, and `canon_knowledge_fts` virtual table). Continuity Engine (`app/core/continuity_engine.py`) and REST API (`/api/v1/continuity`) implemented. Exact world state restoration across restart and state inheritance across scenes with intervening continuity events verified (`tests/test_phase_06_continuity.py` 4/4 passed, 22/22 total project tests passed). |
| **Phase 7** | Novel Ingestion & Season Planning | **PENDING** | Text chunking, entity extraction, 40–50 ep season map before rendering. |
| **Phase 8** | Visual QA v1: DINOv3 & 3-Candidate Reranking | **PENDING** | Whole-subject embeddings, drift tracking, reranking. |
| **Phase 9** | Semantic QA with Qwen3-VL 4B GGUF | **PENDING** | Optional local structured VLM audit via llama.cpp. |
| **Phase 10** | WanGP Backend + MiniMax H3 Short-Shot | **PENDING** | Low-VRAM 480x864 hero generative shots on 8GB VRAM. |
| **Phase 11** | SCAIL-2 Controlled Motion & Motion Library | **PENDING** | Driving motion performances for single-person acting. |
| **Phase 12** | Audio: Voice, Timing & Music | **PENDING** | Chatterbox multilingual TTS, MuseTalk 1.5 lip sync, ACE-Step 1.5 music. |
| **Phase 13** | Foley / Generated SFX | **PENDING** | HunyuanVideo-Foley XL + offload. |
| **Phase 14** | 2.5D Renderer & Deterministic Post | **PENDING** | Parallax/depth still motion + FFmpeg assembly & subtitles. |
| **Phase 15** | Upscaler Benchmark | **PENDING** | SeedVR2 / FlashVSR benchmark on accepted clips. |
| **Phase 16** | Thumbnail System | **PENDING** | Brief agent + FLUX art + programmatic typography + QA. |
| **Phase 17** | Creator Mode E2E | **PENDING** | One-off vertical short pipeline validation. |
| **Phase 18** | Series Mode Pilot (2 -> 5 -> 10 eps) | **PENDING** | Serialized drama continuity verification. |
| **Phase 19** | Optional LTX-2.5 Sandbox | **PENDING** | Separate experimental test environment. |

---

## Action Items / Blockers

- **Immediate:** Install Git, Python 3.11, and FFmpeg (prerequisites for Phase 1).
- **Disk Space Margin:** 268.85 GB available on `C:\`. Keep at least 80 GB free buffer at all times.
