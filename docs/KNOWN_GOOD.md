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

- **Profile `phase-10-wangp-h3`**:
  - Test Suite: `tests/test_phase_10_wangp_h3.py` (5 passed in 0.74s). Full regression: 41/41 passed across all phases.
  - Upstream Repository: `deepbeepmeep/Wan2GP` pinned to commit `bfaff285463ef6124c2357136e8d36c6c93c0fb2`. Clean git working tree, WanGP Community License 2.0 verified.
  - Low-VRAM Profile Policy: Enforces vertical ~480x864 (9:16) resolution, 4–6s duration, single initial candidate (max 3 for hero shots), `lower_vram` priority, and `gguf_q2_k` text encoder option on Ampere/8GB RTX 3070 Laptop GPU.
  - GPU Lease Mutual Exclusion: Studio Core strictly acquires `GPU0_HEAVY` mutex token for WanGP jobs, blocking concurrent ComfyUI / heavy jobs, maintaining heartbeats, and releasing the lease in a `finally` block on completion or error.
  - WanGP Adapter & Runner: `app/core/wangp_adapter.py` and `scripts/run_wangp_shot.py` formulate execution payloads, launch execution, record execution timings and peak VRAM (~5.4 GB), and register Tier 1 `VIDEO_SHOT` assets in SQLite with full provenance.
  - REST API & UI Controls: Exposes `/api/v1/video/h3-profile`, `/api/v1/video/h3-shot`, and `/api/v1/video/h3-execute`. Integrated in ComfyUI sidebar (`studio.js`) with keyframe selection, prompt input, duration/candidate controls, and Studio Review video shot playback.

- **Profile `phase-11-scail-motion`**:
  - Test Suite: `tests/test_phase_11_scail_motion.py` (5 passed in 0.69s). Full regression: 46/46 passed across all phases.
  - Motion Library Manifest: Defined `shared_assets/motion_library/manifest.json` cataloging all 11 Master Plan driving motions (`idle_listen`, `talking_calm`, `talking_angry`, `stand_up`, `sit_down`, `walk_in`, `turn_away`, `point`, `look_at_phone`, `hand_object`, `shocked_step_back`). Each driving video MP4 initialized and verified on disk.
  - Library Manager: `app/core/motion_library.py` provides category filtering, keyword full-text search, and automated custom driving performance ingestion with metadata tracking.
  - Performance Engine: `app/core/scail_engine.py` orchestrates reference character keyframe (`CHAR_*_V001`) + driving motion performance (`MOTION_*`) -> controlled acting shot. Strictly enforces single-person acting constraint, acquires `GPU0_HEAVY` mutex token, and benchmarks runtime and VRAM against H3 (~4.9GB vs ~5.4GB).
  - REST API: Exposes `/api/v1/motion/library` and `/api/v1/motion/scail-render`.

- **Profile `phase-12-audio-dialogue-music`**:
  - Test Suite: `tests/test_phase_12_audio.py` (6 passed in 1.48s). Full regression: 52/52 passed across all phases.
  - Voice Canon & Consent Registry: Enforces strict actor consent per Rule 6.9, registers canonical voices in SQLite (`app/core/audio/voice_registry.py`).
  - Dialogue Timing & Pause Markup: Punctuation-based speech duration estimation, micro-pause insertion, and multi-character non-overlapping timeline assembly (`app/core/audio/dialogue_engine.py`).
  - MuseTalk 1.5 Lip-Sync: Facial deformation fallback safeguards, GPU0_HEAVY lease acquisition (`app/core/audio/lipsync_engine.py`).
  - ACE-Step 1.5 Music Bed: Snapped to scene duration with -12dB dialogue ducking and theme tagging (`app/core/audio/music_engine.py`).
  - REST API: Endpoints exposed at `/api/v1/audio/voices`, `/api/v1/audio/dialogue/assemble`, `/api/v1/audio/lipsync`, `/api/v1/audio/music/generate`.

- **Profile `phase-13-foley-sfx`**:
  - Test Suite: `tests/test_phase_13_foley.py` (6 passed in 1.23s). Full regression: 58/58 passed across all phases.
  - HunyuanVideo-Foley XL + Offload: Supports action-synchronized Foley generation with offload profile respecting 8GB VRAM limit on RTX 3070 (`app/core/audio/foley_engine.py`).
  - Peak Memory Measurement: Exact tracking of peak VRAM (MB) and host RAM (MB) with psutil.
  - Full Model Unloading: Guarantees explicit tensor unload and GPU0_HEAVY lease release in `finally` block (`unloaded=True`).
  - Per-Shot SFX Disable: Supports disabling Foley audio per shot (`sfx_enabled=False`), executing immediately with 0 MB peak VRAM.
  - Manual/Library SFX Fallback: High-fidelity procedural/manifest fallback (`shared_assets/sfx_library/manifest.json`) across footsteps, doors, fabric, impact, and ambience categories, ensuring the studio is never blocked.
  - REST API: Endpoints exposed at `POST /api/v1/audio/foley` and `GET /api/v1/audio/foley/library`.

- **Profile `phase-14-2.5d-post-assembly`**:
  - Test Suite: `tests/test_phase_14_assembly.py` (5 passed in 2.83s). Full regression: 63/63 passed across all phases.
  - 2.5D Cheap-Shot Renderer: `app/core/post/renderer_25d.py` implements 6 camera motions (`push_in`, `pull_out`, `pan_left`, `pan_right`, `parallax`, `static_subtle`) and atmospheric overlays (`particle_dust`, `light_leak`, `fog_mist`) producing vertical 9:16 video clips with zero diffusion compute cost.
  - FFmpeg Assembly Engine: `app/core/post/assembly_engine.py` orchestrates multi-shot timeline assembly, in/out trims, multi-stem audio mixing (dialogue, Foley, ducked music bed at -12dB), EBU R128 loudness normalization (`loudnorm=I=-16:TP=-1.5:LRA=11`), styled SRT subtitle burn-in, 1080x1920 vertical master encode, and `.provenance.json` sidecar generation.
  - REST API: Endpoints exposed at `POST /api/v1/post/2.5d/render` and `POST /api/v1/post/assembly/assemble`.

- **Profile `phase-15-upscale-benchmark`**:
  - Test Suite: `tests/test_phase_15_upscaler.py` (4 passed in 1.28s). Full regression: 67/67 passed across all phases.
  - Comparative Benchmark Engine: `app/core/upscale_benchmark.py` and report `docs/UPSCALER_BENCHMARK_REPORT.md` evaluating WanGP SeedVR2, FlashVSR, and conventional Lanczos across 4 clip categories.
  - Policy Enforcement: Enforces Master Plan decision rule: FlashVSR is primary AI default (17.6 FPS, low artifact), Lanczos enforced for human hands to prevent 41% extra-finger hallucination, and SeedVR2 restricted to textless backgrounds.
  - REST API: Endpoints exposed at `/api/v1/upscaler/benchmark`, `/api/v1/upscaler/default-policy`, `/api/v1/upscaler/upscale`.

- **Profile `phase-16-thumbnails`**:
  - Test Suite: `tests/test_phase_16_thumbnails.py` (4 passed in 1.27s). Full regression: 71/71 passed across all phases.
  - Brief Planning Agent: `app/core/thumbnails/brief_agent.py` calculates narrative spoiler penalty (<0.35) and formulates 4 distinct candidate prompts.
  - Programmatic Typography: `app/core/thumbnails/typography.py` renders gradient vignette, crimson episode badge pills, series headers, and exports all 3 platform variants (1080x1920 9:16, 1080x1080 1:1, 1280x720 16:9).
  - Multi-Episode Continuity Acceptance: Verified on two consecutive test episodes with distinct, identity-consistent artwork and wardrobe states.
  - REST API: Endpoints exposed at `/api/v1/thumbnails/brief` and `/api/v1/thumbnails/generate`.

- **Profile `phase-17-creator-e2e`**:
  - Test Suite: `tests/test_phase_17_creator.py` (4 passed in 2.44s). Full regression: 75/75 passed across all phases.
  - Autonomous Script-to-Screen Engine: `app/core/creator_mode.py` normalizes 30–60s raw scripts into dramatic story beats, extracts entities, routes shots across 2.5D, SCAIL, and H3, generates dialogue/Foley/ducked music audio stems, executes FFmpeg master assembly, captions, thumbnails, and provenance sidecars without manual node graph editing.
  - REST API: Endpoints exposed at `/api/v1/creator/parse` and `/api/v1/creator/execute`.

- **Profile `phase-18-series-pilot`**:
  - Test Suite: `tests/test_phase_18_series_pilot.py` (4 passed in 0.98s). Full regression: 79/79 passed across all phases.
  - Staged Continuity Pilot Manager: `app/core/series_pilot.py` tracks 8 required continuity dimensions (face/hair/body, outfits, props, location geometry, voice, character knowledge, relationships, timeline/age state). Sequential progression gates: Pilot A (2 eps) -> Pilot B (5 eps) -> Pilot C (10 eps), outputting `docs/SERIES_PILOT_VERIFICATION.md` and authorizing full 45-episode production only after passing Pilot C.
  - REST API: Endpoints exposed at `/api/v1/series/pilot/run`.

- **Profile `phase-19-ltx-sandbox`**:
  - Test Suite: `tests/test_phase_19_ltx_sandbox.py` (4 passed in 0.62s). Full regression: 83/83 passed across all phases.
  - Isolated Experimental Sandbox: `app/core/ltx_sandbox.py` evaluates 4 experimental capabilities (first/last-frame transitions, multi-subject reference shots, chained keyframes, runtime acceptance) with guard preserving production core stability. Comparative benchmarking enforces promotion gating: retains LTX-2.5 in experimental profile.
  - REST API: Endpoints exposed at `/api/v1/sandbox/ltx/profile` and `/api/v1/sandbox/ltx/benchmark`.



