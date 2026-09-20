"""In-process durable job worker.

Consumes PENDING render_jobs one at a time (the RTX 3070 can only hold one heavy
model), runs the storyboard handler under the GPU lease, and keeps heartbeats
so a crash is recoverable on restart. Speech-only jobs skip the GPU lease.
"""
from __future__ import annotations

import threading
import time
import traceback
from typing import Optional

from app.core.database import get_connection
from app.core.models import JobKind, JobStatus
from app.core.queue import DurableQueue
from app.core.render_guard import gpu_render_lease
from app.core.run_progress import finish_run, start_run

_thread: Optional[threading.Thread] = None
_stop = threading.Event()
_current_job_id: Optional[str] = None
CPU_ONLY_KINDS = {JobKind.AUDIO_GEN.value}


def current_job_id() -> Optional[str]:
    return _current_job_id


def _next_pending() -> Optional[str]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM render_jobs WHERE status = ? AND kind IN (?,?,?,?) ORDER BY priority DESC, created_at ASC LIMIT 1",
            (JobStatus.PENDING.value, JobKind.KEYFRAME_GEN.value, JobKind.RENDER_SHOT.value, JobKind.AUDIO_GEN.value, JobKind.PACKAGE.value),
        ).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def _run_one(job_id: str) -> None:
    global _current_job_id
    from app.core.storyboard import HANDLERS, StoryboardError

    job = DurableQueue.start_job(job_id)
    if not job or job.status != JobStatus.RUNNING:
        return
    _current_job_id = job_id
    payload = job.payload_json or {}
    start_run(job_id, f"{job.kind} {payload.get('shot_id') or payload.get('storyboard_id') or ''}".strip())
    stop_hb = threading.Event()

    def heartbeat():
        while not stop_hb.wait(10):
            DurableQueue.heartbeat(job_id)

    hb = threading.Thread(target=heartbeat, daemon=True)
    hb.start()
    try:
        handler = HANDLERS[JobKind(job.kind)]
        if job.kind in CPU_ONLY_KINDS:
            outputs = handler(job_id, payload)
        else:
            with gpu_render_lease(f"job_{job.kind}"):
                outputs = handler(job_id, payload)
        DurableQueue.complete_job(job_id, outputs)
        finish_run(job_id, "completed", "Job finished.")
    except StoryboardError as exc:
        DurableQueue.fail_job(job_id, "StoryboardError", str(exc), retryable=False)
        finish_run(job_id, "failed", str(exc))
    except Exception as exc:
        DurableQueue.fail_job(job_id, type(exc).__name__, f"{exc}\n{traceback.format_exc()[-1500:]}", retryable=False)
        finish_run(job_id, "failed", f"{type(exc).__name__}: {exc}")
    finally:
        stop_hb.set()
        hb.join(timeout=5)
        _current_job_id = None


def _loop() -> None:
    while not _stop.is_set():
        try:
            job_id = _next_pending()
            if job_id:
                _run_one(job_id)
                continue
        except Exception:
            traceback.print_exc()
        _stop.wait(1.0)


def start() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="studio-worker", daemon=True)
    _thread.start()


def stop() -> None:
    _stop.set()
    if _thread:
        _thread.join(timeout=5)


def wait_idle(timeout_s: float = 3600) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _current_job_id is None and _next_pending() is None:
            return True
        time.sleep(0.5)
    return False
