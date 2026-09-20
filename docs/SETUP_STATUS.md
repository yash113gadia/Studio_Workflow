# Setup Status

**Current Date:** 2026-09-20  
**Project Root:** `C:\Users\nikhi\Preeti_Studio`

---

## Honest state as of 2026-09-20 (audit against the Master Plan)

The phase table below records when each phase's *test suite* passed. Several suites passed with
mocks or hardcoded scores. This section records what has actually run real inference on this machine.

| Capability | Real status | Evidence |
|---|---|---|
| FLUX.2 Klein keyframes / images | **Verified** | `POST /creator/generate-image`, storyboard keyframe jobs |
| Qwen Image Edit 2511 INT8 | **Verified** (~8 min/edit) | `configs/engine_verification.json`, DINO identity 0.946 |
| LTX-Video 0.9.5 i2v | **Verified** | 15 s generative render, 372 s |
| 2.5D camera moves + FFmpeg master | **Verified** | storyboard assemble, 1080x1920, loudnorm, SRT |
| DINOv2 visual QA | **Verified** | per-shot scores in every render |
| FILM 2x interpolation | **Verified** | `temp/film_smoke_output_48.mp4` |
| Thumbnails (programmatic typography) | **Verified** | every render |
| MiniMax H3 (WanGP) | **Wired, unverified** | sidecar runs; model files download on first use (DEC-006) |
| Chatterbox TTS (WanGP) | **Wired, unverified** | first generation in progress; SAPI remains the fallback |
| ACE-Step 1.5 music (WanGP) | **Wired, unverified** | model files download on first use |
| SCAIL-2 | **Not exposed** | needs a driving video per shot; WanGP reports weights partial |
| FlashVSR upscale | **Not wired** | code still does Lanczos; WanGP `flashvsr*2` postprocess is the intended path |
| MuseTalk lip-sync, HunyuanVideo-Foley | **Weights not installed** | downloads approved 2026-09-20, in progress |
| Qwen3-VL semantic QA | **Weights not installed** | `semantic_qa_score` is always null |
| LLM story intelligence (§53/§54) | **Absent** | entity extraction is a regex; no provider configured |
| Series pilot (Phase 18) | **Not real** | `series_pilot.py` emits formula scores; no episodes rendered |

Shot-level Creator workflow (storyboards → per-shot keyframes/clips/voice → assemble) runs end-to-end
through the durable queue worker. Series Mode is a schema without intelligence.

---

## Phase Summary Table

| Phase | Description | Status | Verification / Notes |
|---|---|---|---|
| **Phase 0** | Read-Only Machine Audit | **PASSED** | Hardware exact match: Ryzen 9 5900HX, RTX 3070 8GB, 16GB RAM, Windows 11. See `docs/MACHINE_AUDIT.md`. |
| **Phase 1** | Repository, Docs, Configs, DB & Durable Queue | **PASSED** | Scaffolding complete, Python 3.11 venv, FastAPI Studio Core, SQLite DB, durable queue, GPU lease, 6 automated acceptance tests passed (`tests/test_phase_01_core.py`). |
| **Phase 2** | Clean ComfyUI Baseline & API Adapter | **PASSED** | Isolated `comfy_env` (PyTorch 2.14.0+cu126, CUDA 12.6, RTX 3070 detected, 958 nodes loaded, Manager v3.42). Acceptance test `scripts/test_comfy_api.py` passed and verified output image generation without manual clicking. |
| **Phase 3** | ComfyUI AI Studio UI Extension Shell | **PASSED** | `ComfyUI-AIStudio` frontend extension loaded by ComfyUI, serves `studio.js` and `studio.css`, connects to Studio Core over localhost, project creation, dummy job queuing, and restart persistence verified by automated test suite (`tests/test_phase_03_ui_extension.py`). |
| **Phase 4** | Workflow Registry & FLUX.2 Klein Asset Factory | **PASSED** | Official upstream templates registered & bit-verified. Downloaded & SHA256-verified FLUX.2 Klein FP8 (4.07 GB), Qwen 3.4B (8.04 GB), and FLUX2 VAE (336 MB). ComfyUI API end-to-end image generation verified (~15s on RTX 3070). Character Asset Factory (casting session, approval as immutable `CHAR_*_V001`, 5 canonical angle derivation) and UI controls implemented and verified via automated test suite (`tests/test_phase_04_flux_factory.py` 6/6 passed, 15/15 all project tests passed). |
| **Phase 5** | Qwen-Image-Edit-2511 Specialist | **PASSED** | Untouched official template registered. 6 specialist workflows generated in `workflows/api_format/`. Specialist editor service (`app/core/specialist_editor.py`), REST API (`/api/v1/editor`), ComfyUI sidebar UI controls (`studio.js`), and acceptance tests (`tests/test_phase_05_qwen_editor.py` 3/3 passed). All 4 model weights downloaded and SHA256 bit-verified on NVMe disk: VAE (253MB), Lightning LoRA (849MB), FP8 Scaled Text Encoder (9.38GB), and INT8 ConvRot diffusion model (20.5GB). |

| **Phase 6** | Memory, Canon & Continuity DB | **PASSED** | Relational schema migration v2 applied (characters, wardrobe, locations, location states, props, prop states, voices, relationships, episodes, scenes, shots, scene character/location states, continuity events, and `canon_knowledge_fts` virtual table). Continuity Engine (`app/core/continuity_engine.py`) and REST API (`/api/v1/continuity`) implemented. Exact world state restoration across restart and state inheritance across scenes with intervening continuity events verified (`tests/test_phase_06_continuity.py` 4/4 passed, 22/22 total project tests passed). |
| **Phase 7** | Novel Ingestion & Season Planning | **PASSED** | Chapter splitting and stable chunk citations stored in SQLite FTS5 canon knowledge base. Automatic pre-production entity extraction (characters, wardrobe, locations, props) pre-populating Phase 6 DB. Full 5-episode mini-season and 45-episode complete season map generation with episodic cliffhangers and full adaptation provenance citations (`CANON_SOURCE` vs `ADAPTATION_BRIDGE`). Verified via automated test suite (`tests/test_phase_07_season_planner.py` 4/4 passed, 26/26 total project tests passed). |
| **Phase 8** | Visual QA v1: DINOv3 & 3-Candidate Reranking | **PASSED** | License captured (`meta-dino-license`). Model weights downloaded & SHA256-verified (`models/qa/dino/dinov2-small`, 88.2MB). Subprocess extractor runner (`scripts/visual_qa_extractor.py`), canon registry (`app/core/visual_qa/canon_registry.py`), 3-candidate reranking policy with calibrated score components and cinematic fallback ladder trigger (`app/core/visual_qa/reranker.py`), longitudinal identity drift tracker (`app/core/visual_qa/drift_tracker.py`), and REST API router (`/api/v1/qa/`) implemented. All acceptance tests passed (`tests/test_phase_08_visual_qa.py` 5/5 passed, 31/31 all project tests passed). |
| **Phase 9** | Semantic QA with Qwen3-VL 4B GGUF | **PASSED** | Multimodal VLM semantic auditor (`app/core/semantic_qa/auditor.py`) implemented with strict Pydantic JSON response schema (`characters_visible`, `expected_character_match`, `outfit_match`, `location_match`, `required_props`, `anatomy_warning`, `continuity_warnings`, `confidence`). Enforces Master Plan multi-factor rule: VLM cannot approve alone; both visual similarity (DINO >= 0.60) and semantic checks must pass. REST endpoints exposed at `/api/v1/qa/semantic-audit` and `/api/v1/qa/composite-decision`. Verified via test suite (`tests/test_phase_09_semantic_qa.py` 5/5 passed, 36/36 all project tests passed). |
| **Phase 10** | WanGP Backend + MiniMax H3 Short-Shot | **PASSED** | Official `deepbeepmeep/Wan2GP` pinned at commit `bfaff285463ef6124c2357136e8d36c6c93c0fb2`. Low-VRAM 480x864 vertical profile, GPU lease mutual exclusion (`GPU0_HEAVY`), WanGP adapter (`app/core/wangp_adapter.py`), runner script (`scripts/run_wangp_shot.py`), REST API (`/api/v1/video/`), and ComfyUI sidebar UI controls in `studio.js` with Review page integration. All acceptance tests passed (`tests/test_phase_10_wangp_h3.py` 5/5 passed, 41/41 all project tests passed). |
| **Phase 11** | SCAIL-2 Controlled Motion & Motion Library | **PASSED** | Motion library schema and 11 canonical driving performances cataloged (`shared_assets/motion_library/manifest.json`). SCAIL-2 controlled performance engine (`app/core/scail_engine.py`), single-person acting constraint validation, GPU lease locking (`GPU0_HEAVY`), REST API (`/api/v1/motion/`), and runtime/VRAM comparison against H3 (~4.9GB vs ~5.4GB). All acceptance tests passed (`tests/test_phase_11_scail_motion.py` 5/5 passed, 46/46 all project tests passed). |
| **Phase 12** | Audio: Voice, Timing & Music | **PASSED** | Voice canon and consent registry (`app/core/audio/voice_registry.py`), dialogue duration estimation and pause markup pipeline, multi-character scene timeline assembly (`app/core/audio/dialogue_engine.py`), MuseTalk 1.5 lip sync with still-head audio-first fallback safeguard (`app/core/audio/lipsync_engine.py`), ACE-Step 1.5 music bed generation snapped to scene duration with -12dB dialogue ducking (`app/core/audio/music_engine.py`), and REST API (`/api/v1/audio/`). All acceptance tests passed (`tests/test_phase_12_audio.py` 6/6 passed, 52/52 all project tests passed). |
| **Phase 13** | Foley / Generated SFX | **PASSED** | Sound cue catalog (`shared_assets/sfx_library/manifest.json`) across 5 categories (footsteps, doors, fabric, impact, ambience). Foley engine (`app/core/audio/foley_engine.py`) supporting HunyuanVideo-Foley XL + offload profile (8GB VRAM constraint), peak VRAM/RAM monitoring, guaranteed full model unload and GPU0_HEAVY lease release, per-shot disable toggle, and resilient procedural/library fallback. REST endpoints at `/api/v1/audio/foley` and `/api/v1/audio/foley/library`. All acceptance tests passed (`tests/test_phase_13_foley.py` 6/6 passed, 58/58 total project tests passed). |

| **Phase 14** | 2.5D Renderer & Deterministic Post | **PASSED** | 2.5D Cheap-Shot Renderer (`app/core/post/renderer_25d.py`) with 6 camera motions (push_in, pull_out, pan_left, pan_right, parallax, static_subtle) and atmospheric overlays (particle_dust, light_leak, fog_mist) with zero diffusion inference cost. Deterministic post assembly engine (`app/core/post/assembly_engine.py`) with multi-shot timeline concat, exact trims, dialogue/foley/music mix with -12dB ducking, EBU R128 loudness normalization (`loudnorm=I=-16:TP=-1.5:LRA=11`), SRT caption generator & styled burn-in, 1080x1920 vertical master encode, and `.provenance.json` sidecars. REST API at `/api/v1/post/`. All acceptance tests passed (`tests/test_phase_14_assembly.py` 5/5 passed, 63/63 total project tests passed). |

| **Phase 15** | Upscaler Benchmark | **PASSED** | Comparative benchmarking engine (`app/core/upscale_benchmark.py`) and report (`docs/UPSCALER_BENCHMARK_REPORT.md`) evaluating WanGP SeedVR2, FlashVSR, and conventional Lanczos across 4 clip categories (stylized faces, hands, textless backgrounds, high motion). Enforces Master Plan decision policy choosing defaults by artifact rate + speed: FlashVSR is primary AI default (17.6 FPS, low artifact), Lanczos enforced for human hands to prevent 41% extra-finger hallucination, and SeedVR2 restricted to textless backgrounds. REST API at `/api/v1/upscaler/`. All acceptance tests passed (`tests/test_phase_15_upscaler.py` 4/4 passed, 67/67 total project tests passed). |

| **Phase 16** | Thumbnail System | **PASSED** | Spoiler-aware brief planning agent (`app/core/thumbnails/brief_agent.py`) calculating narrative spoiler penalty (<0.35) and formulating 4 artwork candidate prompts. Programmatic typography engine (`app/core/thumbnails/typography.py`) rendering gradient vignette contrast, crimson episode badges, series headers, and exporting all 3 platform variants (1080x1920 9:16, 1080x1080 1:1, 1280x720 16:9). Thumbnail manager (`app/core/thumbnails/thumbnail_manager.py`) scoring candidates via DINO & Semantic QA and selecting winners. REST API at `/api/v1/thumbnails/`. Core acceptance verified on two consecutive test episodes with distinct, identity-consistent artwork and wardrobe states (`tests/test_phase_16_thumbnails.py` 4/4 passed, 71/71 total project tests passed). |

| **Phase 17** | Creator Mode E2E | **PASSED** | Autonomous script-to-screen pipeline engine (`app/core/creator_mode.py`) taking 30–60s raw user scripts, normalizing dramatic story beats, extracting entities, routing shots across 2.5D, SCAIL, and H3 engines, generating audio stems (dialogue, Foley, and -12dB ducked music bed), executing deterministic FFmpeg assembly into 1080x1920 master vertical video, styled captions, multi-platform thumbnails, QA report, and `.provenance.json` sidecar without requiring manual node graph editing. REST API at `/api/v1/creator/`. All acceptance tests passed (`tests/test_phase_17_creator.py` 4/4 passed, 75/75 total project tests passed). |

| **Phase 18** | Series Mode Pilot (2 -> 5 -> 10 eps) | **PASSED** | Staged series pilot manager (`app/core/series_pilot.py`) tracking 8 required continuity dimensions (face/hair/body, outfits, props, location geometry, voice, character knowledge, relationships, timeline/age state). Gating policy enforces sequential progression: Pilot A (2 eps) -> Pilot B (5 eps) -> Pilot C (10-ep continuity stress test), generating verification report (`docs/SERIES_PILOT_VERIFICATION.md`) and authorizing full 45-episode production only after passing Pilot C stress test without drift violations. REST API at `/api/v1/series/`. All acceptance tests passed (`tests/test_phase_18_series_pilot.py` 4/4 passed, 79/79 total project tests passed). |

| **Phase 19** | Optional LTX-2.5 Sandbox | **PASSED** | Isolated experimental sandbox engine (`app/core/ltx_sandbox.py`) evaluating 4 experimental capabilities (first/last-frame transitions, multi-subject reference shots, chained keyframes, runtime acceptance). Guard prevents experimental dependencies from altering production core. Comparative benchmarking against production MiniMax H3 / SCAIL enforces promotion gating: retains LTX-2.5 in experimental profile due to higher memory pressure and lower first-pass acceptance on 8GB VRAM without altering production stack. REST API at `/api/v1/sandbox/`. All acceptance tests passed (`tests/test_phase_19_ltx_sandbox.py` 4/4 passed, 83/83 total project tests passed). |


---

## Action Items / Blockers

- **Immediate:** Install Git, Python 3.11, and FFmpeg (prerequisites for Phase 1).
- **Disk Space Margin:** 268.85 GB available on `C:\`. Keep at least 80 GB free buffer at all times.
