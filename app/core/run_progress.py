"""Thread-safe live Creator progress and local hardware telemetry."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
import subprocess
import threading
import time
import urllib.request
from typing import Any, Dict, Optional

import psutil


_lock = threading.RLock()
_runs: Dict[str, Dict[str, Any]] = {}
_latest_run_id: Optional[str] = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_run(run_id: str, title: str, total_shots: int = 0) -> None:
    global _latest_run_id
    with _lock:
        _latest_run_id = run_id
        _runs[run_id] = {
            "run_id": run_id,
            "title": title,
            "status": "running",
            "stage": "initializing",
            "progress": 1,
            "current_shot": 0,
            "total_shots": total_shots,
            "started_at": _now(),
            "started_monotonic": time.monotonic(),
            "finished_at": None,
            "finished_monotonic": None,
            "events": deque(maxlen=400),
        }
    emit(run_id, "initializing", "Creator request accepted; acquiring the GPU render lease.", 1)


def emit(
    run_id: str,
    stage: str,
    message: str,
    progress: Optional[int] = None,
    *,
    level: str = "info",
    current_shot: Optional[int] = None,
    total_shots: Optional[int] = None,
) -> None:
    event = {"time": _now(), "stage": stage, "level": level, "message": message}
    with _lock:
        run = _runs.get(run_id)
        if not run:
            return
        run["stage"] = stage
        if progress is not None:
            run["progress"] = max(0, min(100, int(progress)))
        if current_shot is not None:
            run["current_shot"] = current_shot
        if total_shots is not None:
            run["total_shots"] = total_shots
        run["events"].append(event)
    print(f"[Creator:{run_id}][{stage}] {message}", flush=True)


def finish_run(run_id: str, status: str, message: str) -> None:
    progress = 100 if status == "completed" else None
    emit(run_id, status, message, progress, level="error" if status == "failed" else "info")
    with _lock:
        run = _runs.get(run_id)
        if run:
            run["status"] = status
            run["finished_at"] = _now()
            run["finished_monotonic"] = time.monotonic()


def _gpu_snapshot() -> Dict[str, Any]:
    command = [
        "nvidia-smi",
        "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
        "--format=csv,noheader,nounits",
    ]
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        value = subprocess.run(command, capture_output=True, text=True, timeout=2, creationflags=flags, check=True).stdout.strip()
        gpu, used, total, temp, power = [part.strip() for part in value.split(",")]
        return {
            "utilization_percent": float(gpu),
            "vram_used_mib": float(used),
            "vram_total_mib": float(total),
            "temperature_c": float(temp),
            "power_w": float(power),
        }
    except Exception as exc:
        return {"error": str(exc)}


def _comfy_snapshot() -> Dict[str, Any]:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8188/queue", timeout=2) as response:
            queue = json.load(response)
        return {
            "online": True,
            "running": len(queue.get("queue_running", [])),
            "pending": len(queue.get("queue_pending", [])),
        }
    except Exception as exc:
        return {"online": False, "running": 0, "pending": 0, "error": str(exc)}


def _studio_pending() -> int:
    try:
        from app.core.database import get_connection
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM render_jobs WHERE status IN ('PENDING', 'RUNNING')"
            ).fetchone()
            return int(row["count"] if row else 0)
        finally:
            conn.close()
    except Exception:
        return 0


def snapshot(run_id: Optional[str] = None) -> Dict[str, Any]:
    with _lock:
        selected = run_id or _latest_run_id
        run = _runs.get(selected) if selected else None
        if run:
            data = {key: value for key, value in run.items() if key not in {"events", "started_monotonic", "finished_monotonic"}}
            data["events"] = list(run["events"])
            endpoint = run.get("finished_monotonic") or time.monotonic()
            data["elapsed_s"] = round(endpoint - run["started_monotonic"], 1)
        else:
            data = {
                "run_id": selected, "status": "idle", "stage": "idle", "progress": 0,
                "events": [], "elapsed_s": 0, "current_shot": 0, "total_shots": 0,
            }
    memory = psutil.virtual_memory()
    data["system"] = {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_percent": memory.percent,
        "ram_used_gib": round(memory.used / 1024**3, 2),
        "ram_total_gib": round(memory.total / 1024**3, 2),
        "gpu": _gpu_snapshot(),
        "comfy": _comfy_snapshot(),
        "studio_pending": _studio_pending(),
    }
    return data
