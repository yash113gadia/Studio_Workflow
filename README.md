> **Current implementation status (20 September 2026):** The working Creator path is local FLUX imagery, clean camera motion, Windows speech, and FFmpeg assembly. Real-motion LTX-Video 0.9.5 inference has also been validated on a short sample and is the default Creator mode. Several specialist engines and benchmark claims below describe the original plan or mocks, not verified production inference. See [the quality repair report](docs/QUALITY_REPAIR_2026-09-20.md) for measured results and limits.

# 🎬 Preeti Studio — Autonomous Local AI Film & Vertical Drama OS

**Preeti Studio** is a locally operated, production-grade AI video studio operating system designed to produce:
1. **Serialized Vertical Dramas (40–50 episodes)** from uploaded novels, enforcing 8-dimension continuity across characters, wardrobe, locations, props, voices, and timeline age state.
2. **One-Off / Random Vertical Videos (Creator Mode)** from raw text scripts in a single autonomous pipeline without manual node graph editing.

Engineered with strict hardware governance for consumer hardware (**RTX 3070 8GB VRAM / 16GB Host RAM**), featuring global GPU mutual exclusion (`GPU0_HEAVY`), automated multi-factor visual & semantic QA auditing, and complete cryptographic provenance sidecars.

---

## 🏗️ Architecture & Engines

| Capability | Engine / Architecture | Hardware Tier |
|---|---|---|
| **Character Casting & Concept Art** | FLUX.2 Klein 4B FP8 + Qwen 3.4B Text Encoder | GPU (8 GB) |
| **Wardrobe & Specialist Edits** | Qwen-Image-Edit 2511 INT8 ConvRot + 4-Step Turbo | GPU (8 GB) |
| **Cinematic Generative Video** | MiniMax H3 Ref2VA Pruned INT8 + Qwen3-VL GGUF DiT | GPU + RAM Offload |
| **Controlled Performance / Motion** | Wan 2.1 / SCAIL-2 14B Quanto INT8 | GPU (8 GB) |
| **Cheap-Shot 2.5D Camera** | Camera matrix projection (Push/Pull/Pan/Parallax) | CPU / Zero VRAM |
| **Soundtrack & Leitmotifs** | ACE-Step 1.5 Music Transformer + Vocoder | GPU (8 GB) |
| **Voice & Speech Synthesis** | Chatterbox Multilingual TTS with voice consent | GPU / CPU |
| **Lip Synchronization** | MuseTalk 1.5 | GPU (8 GB) |
| **Sound Effects (Foley)** | HunyuanVideo-Foley XL + Offload / Sound Library | GPU (8 GB) |
| **Video Super-Resolution** | FlashVSR v1.1 (Temporal Consistency Anti-Flicker) | GPU (8 GB) |
| **Visual QA & Drift Guard** | DINOv2 Small (Longitudinal Cosine Similarity) | CPU / Lightweight |
| **Relational Memory & Canon** | SQLite in WAL mode (28 tables, FTS5 Indexing) | Zero Compute |

---

## 🚀 Quickstart: Set Up on a New Windows PC

### 1. Requirements
* **OS:** Windows 10/11
* **GPU:** NVIDIA RTX. Verified on an 8 GB RTX 3070; less VRAM is untested. Driver 580+ recommended; RTX 50-series requires it.
* **RAM:** ≥ 16 GB
* **Disk:** ≥ 40 GB free (core models ~24 GB; Python environments and ComfyUI take several GB more)
* Python 3.11 and FFmpeg are installed by setup if missing. Git is optional.

### 2. Get the Code
Put it in a short path such as `C:\Preeti_Studio` (long paths can break the PyTorch install):
```powershell
git clone https://github.com/yash113gadia/Studio_Workflow.git C:\Preeti_Studio
```
Or download the ZIP from GitHub (Code → Download ZIP) and extract it to a short path like `C:\Preeti_Studio`. With a ZIP, Windows may show "Windows protected your PC" when you open the `.bat` files: click **More info → Run anyway**.

### 3. Run Setup (one time)
Double-click **`Setup_Preeti_Studio.bat`**. It:
1. Checks the GPU, NVIDIA driver, RAM and disk, and picks the matching PyTorch CUDA build.
2. Installs Python 3.11 (winget, or python.org) and FFmpeg (into `tools\ffmpeg`) if missing.
3. Creates `environments\studio_core_env` and `environments\comfy_env`, downloads ComfyUI at the verified commit, and confirms PyTorch can see the GPU.
4. Downloads and SHA256-verifies the core models: FLUX.2 Klein 4B, LTX-Video 0.9.5, T5 encoder, DINOv2 (`scripts/download_core_models.py`, no Hugging Face token needed).
5. Starts this PC on an empty database (the original PC's is kept as `database\studio_from_original_pc.db.bak`).
6. Creates a **Preeti Studio** desktop shortcut, starts the studio, and runs `scripts/smoke_test.py`: a real FLUX image, a 2-second LTX clip, a Windows voice line and an FFmpeg check.

Setup takes an hour or more, mostly downloading. If it stops, fix the reported problem and run it again; finished steps are skipped and downloads resume. The log is `logs\setup.log`.

### 4. Use the Studio
Double-click the **Preeti Studio** desktop icon (or `Launch_Preeti_Studio.bat`). It starts ComfyUI and the Studio server and opens:

* **Studio Web UI:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
* **ComfyUI:** [http://127.0.0.1:8188](http://127.0.0.1:8188)
* **FastAPI Backend OpenAPI / Swagger:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Stop the background services with `scripts/stop_studio.ps1` and `scripts/stop_comfy.ps1`.

### 5. Optional: Specialist Engines
`scripts/download_staged_models.py` fetches ~60 GB of additional weights (MiniMax H3, SCAIL-2, FlashVSR, ACE-Step) for engines that are wired but **not verified** (see `docs/SETUP_STATUS.md`). They also need the WanGP runtime. The Creator path above does not use them.

### 6. Developer Checks
```powershell
# Model weights and disk headroom
& ".\environments\studio_core_env\Scripts\python.exe" scripts/check_models.py

# Post-install smoke test (Studio and ComfyUI must be running)
& ".\environments\studio_core_env\Scripts\python.exe" scripts/smoke_test.py

# Test suite
$env:PYTHONPATH="."
& ".\environments\studio_core_env\Scripts\pytest.exe" -v tests/
```

---

## 📜 Key Endpoints (REST API)

| Route | Function |
|---|---|
| `/api/v1/creator/generate` | Autonomous 30–60s Creator Mode pipeline (script-to-screen) |
| `/api/v1/series/pilot` | Evaluates staged continuity pilots (Pilot A, B, or C) |
| `/api/v1/editor/action` | Specialist Qwen edits (wardrobe swap, angles, prop cleanup) |
| `/api/v1/video/h3/render` | MiniMax H3 cinematic video generation |
| `/api/v1/motion/scail/render` | SCAIL-2 controlled character motion transfer |
| `/api/v1/audio/synthesize` | Multi-speaker dialogue assembly with ducked background score |
| `/api/v1/post/assemble` | 2.5D camera renders, SRT captions, and master vertical encode |
| `/api/v1/thumbnails/generate` | Multi-aspect thumbnail generation (9:16, 1:1, 16:9) |

---

## 🔒 Governance & License Compliance
See [docs/LICENSES_AND_MODEL_TERMS.md](docs/LICENSES_AND_MODEL_TERMS.md) for commercial licensing terms across all upstream repositories and checkpoints.
