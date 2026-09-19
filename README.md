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

## 🚀 Quickstart & Machine Replication Guide

### 1. Prerequisites
* **OS:** Windows 10/11 (or Linux with CUDA support)
* **GPU:** NVIDIA GPU with $\ge 8\text{ GB}$ VRAM (CUDA 12.x compatible)
* **RAM:** $\ge 16\text{ GB}$ System RAM
* **Storage:** $\ge 120\text{ GB}$ free disk space (models: ~70 GB, safety buffer: $\ge 80\text{ GB}$)
* **Tools:** Python 3.11, Git, FFmpeg

---

### 2. Clone the Repository
```bash
git clone <YOUR_GITHUB_REPO_URL> Preeti_Studio
cd Preeti_Studio
```

---

### 3. Setup Python Runtime
Create the core virtual environment and install dependencies:
```powershell
python -m venv environments/studio_core_env
.\environments\studio_core_env\Scripts\pip.exe install -r requirements.txt
```

---

### 4. Download Open-Source Model Weights (Autonomous)
Preeti Studio includes an automated, resumable downloader with HTTP Range support and strict disk safety checks:

```powershell
# Set your Hugging Face access token
$env:HF_TOKEN = "your_hf_token_here"

# Launch the autonomous downloader
& ".\environments\studio_core_env\Scripts\python.exe" scripts/download_staged_models.py
```
This will download and verify all 23 neural model files into `models/`.

---

### 5. Verify Installation
Run the built-in integrity auditor and system healthcheck:
```powershell
# Check model weights and disk headroom
& ".\environments\studio_core_env\Scripts\python.exe" scripts/check_models.py

# Verify SQLite WAL database, 28 tables, and GPU mutex
& ".\environments\studio_core_env\Scripts\python.exe" scripts/healthcheck.py

# Run the 83-test acceptance test suite
$env:PYTHONPATH="."
& ".\environments\studio_core_env\Scripts\pytest.exe" -v tests/
```

---

### 6. Launch the Studio
Start both the FastAPI brain and ComfyUI dashboard:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_studio.ps1
```

* **ComfyUI UI Dashboard:** [http://127.0.0.1:8188](http://127.0.0.1:8188) (with custom `ComfyUI-AIStudio` sidebar)
* **FastAPI Backend OpenAPI / Swagger:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

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
