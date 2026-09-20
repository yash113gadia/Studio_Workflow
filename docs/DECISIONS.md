# Architectural Decisions & Deviations Log (DECISIONS.md)

This log records every deliberate architectural decision, deviation, and upstream workaround per Section 0.1 of the Master Plan.

---

### [DEC-001] Project Root Directory Location
- **Date:** 2026-09-19
- **Decision:** Establish project root at `C:\Users\nikhi\Preeti_Studio`.
- **Context:** The Master Plan recommended `D:\AIStudio` if D: exists or `C:\AIStudio`. The machine audit verified no `D:\` drive exists. The user explicitly requested execution in `preeti_studio`.
- **Rationale:** Aligns with user request while keeping paths contained within a clean, dedicated workspace directory on the primary NVMe SSD (268 GB free).

### [DEC-002] Studio Core as an Independent Sidecar
- **Date:** 2026-09-19
- **Decision:** Run Studio Core as a standalone FastAPI service on `127.0.0.1:8000`, communicating via HTTP/SSE with the ComfyUI extension.
- **Rationale:** Crash isolation. ComfyUI workflow execution errors or restarts must never corrupt the SQLite story database, continuity ledger, or durable job queue.

### [DEC-003] Strict Global GPU Mutex
- **Date:** 2026-09-19
- **Decision:** Implement a centralized database/file backed lease token `GPU0_HEAVY` in Studio Core.
- **Rationale:** With 8 GB VRAM, concurrent heavy diffusion/video/audio GPU workloads cause immediate CUDA OOMs or severe driver-level paging stalls. Only one heavy process may hold the lease at a time.

### [DEC-004] Standalone Studio web app instead of the ComfyUI sidebar as the primary UI
- **Date:** 2026-09-20
- **Decision:** The day-to-day operator surface is `app/static/` served by Studio Core on `:8000` (shot-level storyboard workspace). The `ComfyUI-AIStudio` sidebar (Phase 3) remains for engineering.
- **Context:** Master Plan §10 wanted the ComfyUI sidebar as the product surface. A per-shot workspace with candidate galleries, drag reordering, inspectors and a jobs dock is materially better as its own page than as a Gradio/Vue sidebar tab, and it keeps ComfyUI replaceable (§0.6).

### [DEC-005] WanGP runs as a resident sidecar process
- **Date:** 2026-09-20
- **Decision:** `scripts/wangp_service.py` keeps one warm `WanGPSession` (official `shared/api.py`) on `127.0.0.1:8199`; Studio Core calls it over HTTP and holds `GPU0_HEAVY` around every call.
- **Rationale:** WanGP needs its own environment (torch 2.10 cu130 vs. Studio Core's) and a ~1 minute warm-up; a resident process avoids reloading per shot. No Gradio UI scraping (§6.3).
- **Deviation:** `requirements.txt` pins a nightly `onnxruntime-gpu` from an Azure DevOps feed that does not resolve from this network; installed PyPI `onnxruntime-gpu>=1.22` instead (only used by rembg/audio-separator). `antlr4-python3-runtime==4.9.3` needs `setuptools<72` to build on Windows.

### [DEC-006] Existing MiniMax H3 weights are stale; WanGP fetches current files
- **Date:** 2026-09-20
- **Context:** `MiniMax-H3-*-pruned_int8_convrot.safetensors` (21 GB, downloaded earlier) predates WanGP's `pruned_rank8` AdaLN pruning format (`models/minimax_h3/prune_checkpoint.py`). WanGP at pinned commit `bfaff28` reports them as missing.
- **Decision:** Do not rename or patch. WanGP downloads the matching `_rank8_int8_convrot` file on first H3 use; the old files can be deleted once H3 is verified.

### [DEC-007] Engine verification state is data, not code
- **Date:** 2026-09-20
- **Decision:** `configs/engine_verification.json` records which engines passed real inference on this machine and overrides the static defaults in `app/core/capabilities.py`.
- **Rationale:** Previous status strings were hand-edited and drifted from reality (e.g. Series pilot "PASSED" with formula-generated scores). Only verified engines are selectable in the UI.
