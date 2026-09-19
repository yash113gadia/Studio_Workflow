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
| **ComfyUI Core** | v0.36.0 (commit `3c80da7f87ee359b2d06f107cb3c0797079dfbbb`) | Yes (Phase 2) | Official upstream, 958 nodes, PyTorch 2.14.0+cu126, CUDA 12.6, RTX 3070 8GB |
| **ComfyUI-Manager** | v3.42 | Yes (Phase 2) | In `custom_nodes/ComfyUI-Manager` |
| **ComfyUI-AIStudio** | v0.1.0 | Yes (Phase 3) | Custom sidebar extension in `custom_nodes/ComfyUI-AIStudio` |
| **FLUX.2 Klein 4B FP8** | Black Forest Labs / Comfy-Org | Yes (Phase 4) | `models/image/diffusion_models/flux-2-klein-4b-fp8.safetensors` (SHA256: `97ed34fe...`) |
| **Qwen 3.4B Text Encoder** | Comfy-Org / Qwen | Yes (Phase 4) | `models/image/text_encoders/qwen_3_4b.safetensors` (SHA256: `6c671498...`) |
| **FLUX2 VAE** | Comfy-Org | Yes (Phase 4) | `models/image/vae/flux2-vae.safetensors` (SHA256: `868fe7b3...`) |

---

## Passed Verification Profiles

- **Profile `phase-01-core-foundation`**:
  - Test Suite: `tests/test_phase_01_core.py` (6 passed in 0.80s).
  - Verified: Project CRUD, durable queue persistence in SQLite, process crash simulation & stale `RUNNING` recovery, global GPU mutex lease mutual exclusion (`GPU0_HEAVY`), `/api/v1/health` and `/api/v1/jobs` endpoints.
  - Startup / Shutdown scripts verified: `scripts/start_studio.ps1`, `scripts/stop_studio.ps1`.

- **Profile `phase-02-comfy-baseline`**:
  - Test Script: `scripts/test_comfy_api.py`.
  - Verified: ComfyUI server startup on `127.0.0.1:8188`, `/system_stats` verified with CUDA RTX 3070, `/object_info` (958 nodes registered), programmatic queue submission of deterministic workflow (`LoadImage` -> `SaveImage`), output image generated at `C:\Users\nikhi\Preeti_Studio\services\comfyui\ComfyUI\output\api_acceptance_test_00001_.png` (448 bytes) without manual clicking.
  - Extra model paths verified: `extra_model_paths.yaml` mapped to `Preeti_Studio\models`.

- **Profile `phase-03-comfy-studio-ui-shell`**:
  - Test Suite: `tests/test_phase_03_ui_extension.py` (3 passed in 2.65s).
  - Verified: Frontend extension assets served via ComfyUI static web server (`/extensions/ComfyUI-AIStudio/studio.js`, `studio.css`), bi-directional integration with Studio Core API (`127.0.0.1:8000`), project creation, dummy job queuing in durable SQLite queue, dynamic UI status updates, and full persistence across simulated ComfyUI server restarts.

- **Profile `phase-04-flux-asset-factory`**:
  - Test Suite: `tests/test_phase_04_flux_factory.py` (6 passed in 1.18s). Full regression: 15/15 passed across all phases.
  - E2E Generation: Verified live ComfyUI generation using official FLUX.2 Klein text-to-image architecture (`scripts/test_flux_e2e.py`). Generated `flux2_klein_e2e_test_00001_.png` in ~15s on RTX 3070 (8GB VRAM).
  - Model Verification: Bit-level SHA256 checksum verification of all 3 required weights on local NVMe disk (`flux2-vae`, `flux-2-klein-4b-fp8`, `qwen_3_4b`).
  - Workflows: 2 official untouched upstream workflows cataloged with SHA256 in `docs/UPSTREAM_MANIFEST.md`; 5 Studio parametric workflows registered in `workflows/api_format/`.
  - Character Asset Factory: Casting session with 3 deterministic candidates, promotion of candidate to canonical `CHAR_*_V001`, strict immutability protection preventing overwrites, and derivation of 5 canonical angles (`FRONT_NEUTRAL`, `THREE_QUARTER_LEFT`, `THREE_QUARTER_RIGHT`, `PROFILE_LEFT`, `PROFILE_RIGHT`) with complete provenance tracking.

- **Profile `phase-06-memory-continuity`**:
  - Test Suite: `tests/test_phase_06_continuity.py` (4 passed in 0.77s). Full regression: 22/22 passed across all phases.
  - Relational Schema: 25 tables active in SQLite WAL mode covering characters, wardrobe packs, recurring locations, location states, props, prop states, voice profiles, character relationships, episodes, scenes, shots, scene world state snapshots, continuity events, and `canon_knowledge_fts` virtual table.
  - FTS5 Text Search: Sub-millisecond full-text indexed queries over character visual descriptions, wardrobe attire, set descriptions, and prop significance.
  - World State Snapshot & Restoration: Exact bit-for-bit restoration of character wardrobe, held prop, injury state, emotional state, and blocking marks across database/process restarts.
  - Scene Continuity Inheritance Machine: Autonomous state propagation from Scene N to Scene N+1 preserving character appearance and held items, with deterministic state transitions when intervening continuity events (wardrobe change, injury sustained, prop dropped) occur with narrative rationale.

- **Profile `phase-07-novel-season-planner`**:
  - Test Suite: `tests/test_phase_07_season_planner.py` (4 passed in 1.23s). Full regression: 26/26 passed across all phases.
  - Ingestion Engine: Structural chapter detection across headings and stable chunk citations indexed in SQLite FTS5 (`app/core/novel_parser.py`).
  - Pre-Production Entity Extractor: Autonomous discovery of recurring characters, core wardrobe, locations, and narrative props pre-populating Phase 6 DB (`app/core/season_planner.py`).
  - Season Planning Architecture: Complete 5-episode mini-season and 45-episode full season map generation with episodic cliffhangers (`revelation`, `peril`, `betrayal`, `dilemma`) designed for vertical retention.
  - Adaptation Provenance: Every adaptation decision tagged as either citeable `CANON_SOURCE` (referencing deterministic chunk IDs) or `ADAPTATION_BRIDGE` original material.

- **Profile `phase-08-visual-qa-v1`**:
  - Test Suite: `tests/test_phase_08_visual_qa.py` (5 passed). Full regression: 31/31 passed across all phases.
  - Model Weights & Licensing: Meta DINO model (`models/qa/dino/dinov2-small`, 88,249,960 bytes, SHA256 `ae1e99fcefd534ed978cdeb8326f08030c96e28b7a81ffcbc98a857c84d14be1`) installed and verified with license captured in `docs/LICENSES_AND_MODEL_TERMS.md` and `configs/models.yaml`.
  - Feature Extractor Architecture: Subprocess extractor runner `scripts/visual_qa_extractor.py` executing inside `comfy_env` (PyTorch 2.14.0+cu126 + Transformers 5.17.0) to keep `studio_core_env` cleanly isolated without PyTorch/CUDA dependency bloat. Produces 384-dimensional unit-normalized dense & CLS representations on CPU (<40ms) without consuming GPU VRAM.
  - Canonical Reference Registry: Database caching of Tier 0 canonical identity and location embeddings in `visual_embeddings` table.
  - Three-Candidate Reranking Policy: Evaluates 3 test candidates across whole-subject similarity, identity crop similarity, location similarity, and style similarity. Normalizes components and computes calibrated composite score. Automatically tags top passing candidate as `ACCEPTED` (winner), passing alternatives as `ALTERNATIVE`, and rejects sub-threshold candidates with logged reasons (`REJECT_IDENTITY_DRIFT`, `REJECT_LOW_COMPOSITE`).
  - Fallback Ladder Trigger: Deterministically triggers `TRIGGER_CINEMATIC_FALLBACK_LADDER_ATTEMPT_2` when all 3 candidates fail acceptance thresholds.
  - Longitudinal Drift Tracker: Tracks character identity similarity to Tier 0 across sequential episodes and scenes in `qa_drift_logs`. Computes rolling moving average and raises `CHARACTER_IDENTITY_DRIFT_ALERT` when drift delta exceeds 0.15.
  - REST API Router: Full REST API exposed at `/api/v1/qa/` registered in `app/main.py` for embedding extraction, canonical registration, candidate reranking, and drift retrieval.

- **Profile `phase-09-semantic-qa`**:
  - Test Suite: `tests/test_phase_09_semantic_qa.py` (5 passed). Full regression: 36/36 passed across all phases.
  - Strict Schema Enforcement: Pydantic models in `app/core/semantic_qa/schema.py` enforcing exact Master Plan JSON schema (`characters_visible`, `expected_character_match`, `outfit_match`, `location_match`, `required_props`, `anatomy_warning`, `continuity_warnings`, `confidence`).
  - Multimodal VLM Semantic Auditor: `app/core/semantic_qa/auditor.py` supports on-demand localhost OpenAI-compatible endpoint / llama.cpp subprocess with prompt formulation for prop presence (`PROP_RED_DIARY`), wardrobe alignment, and facial/hand anatomy inspection.
  - Multi-Factor Decision Engine: Implements the fundamental Master Plan constraint that "VLM cannot approve alone; it contributes to QA." A candidate is only approved when BOTH Visual QA (DINO visual embedding score >= 0.60) and Semantic QA (no anatomy distortions, expected character match, and all mandatory scene props verified) pass simultaneously.
  - REST Endpoints: Added `/api/v1/qa/semantic-audit` and `/api/v1/qa/composite-decision` to the Studio Core REST API.
