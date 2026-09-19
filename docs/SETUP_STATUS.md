# Setup Status

**Current Date:** 2026-09-19  
**Current Phase:** Phase 0 Completed, Transitioning to Phase 1  
**Project Root:** `C:\Users\nikhi\Preeti_Studio`

---

## Phase Summary Table

| Phase | Description | Status | Verification / Notes |
|---|---|---|---|
| **Phase 0** | Read-Only Machine Audit | **PASSED** | Hardware exact match: Ryzen 9 5900HX, RTX 3070 8GB, 16GB RAM, Windows 11. See `docs/MACHINE_AUDIT.md`. |
| **Phase 1** | Repository, Docs, Configs, DB & Durable Queue | **IN PROGRESS** | Scaffold directories, set up Python 3.11, FastAPI, SQLite DB, GPU lease, unit tests. |
| **Phase 2** | Clean ComfyUI Baseline & API Adapter | **PENDING** | Isolated ComfyUI venv, API test script `scripts/test_comfy_api.py`. |
| **Phase 3** | ComfyUI AI Studio UI Extension Shell | **PENDING** | Frontend sidebar extension registering "AI Studio" tab. |
| **Phase 4** | Workflow Registry & FLUX.2 Klein Asset Factory | **PENDING** | FLUX.2 Klein 4B distilled, test character casting & 5 angles. |
| **Phase 5** | Qwen-Image-Edit-2511 Specialist | **PENDING** | INT8 ConvRot image repair & clothing swap specialist. |
| **Phase 6** | Memory, Canon & Continuity DB | **PENDING** | Hierarchical state, world state snapshots, SQLite FTS5. |
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
