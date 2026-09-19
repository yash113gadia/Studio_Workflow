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
