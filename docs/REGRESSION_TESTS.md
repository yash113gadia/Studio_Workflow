# Regression Test Protocol (REGRESSION_TESTS.md)

Tests that must pass before any updates or promotions are approved in the studio.

---

## Core Phase Regression Battery

### Phase 1: Studio Core & Queue Resilience
1. Studio Core startup & `/api/v1/health` check.
2. Dummy job enqueue, status transitions, and SQLite persistence.
3. Sudden process termination while job is `RUNNING` ➔ restart Studio Core ➔ verify job recovery / heartbeat timeout.
4. Concurrent GPU lease acquisition contention (second worker blocked until first releases).

### Phase 2: ComfyUI Baseline & API
1. ComfyUI startup and health `/system_stats`.
2. Programmatic execution of deterministic test workflow via `/prompt` + WebSocket listener.
3. Verification of output image file generation.

### Phase 3: Extension UI Integration
1. Sidebar registration verification.
2. Localhost communication between ComfyUI frontend and Studio Core.
3. Real-time status update without browser refresh.

### Phase 4: FLUX.2 Klein Asset Factory
1. Generation of 3 casting candidates for a character.
2. Approval of canonical reference and derivation of 5 distinct compositions without identity drift.
