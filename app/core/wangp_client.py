"""HTTP client for the WanGP sidecar (scripts/wangp_service.py)."""
from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
BASE = "http://127.0.0.1:8199"
ProgressCallback = Optional[Callable[[str, int], None]]


class WanGPUnavailable(RuntimeError):
    pass


def _request(method: str, path: str, body: Optional[Dict[str, Any]] = None, timeout: float = 30) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise WanGPUnavailable(f"WanGP service {exc.code}: {detail[:300]}") from exc
    except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
        raise WanGPUnavailable(f"WanGP service is not running on {BASE}: {exc}") from exc


def health() -> Dict[str, Any]:
    try:
        return _request("GET", "/health", timeout=5)
    except WanGPUnavailable as exc:
        return {"ready": False, "error": str(exc), "running": False}


def is_ready() -> bool:
    return bool(health().get("ready"))


def ensure_service(wait_s: float = 240) -> None:
    """Start the sidecar if it is not running and wait until its session is warm."""
    status = health()
    if status.get("ready"):
        return
    if "not running" in (status.get("error") or ""):
        python = ROOT / "environments" / "wangp_env" / "Scripts" / "python.exe"
        log = open(ROOT / "logs" / "wangp_service.log", "ab")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen([str(python), str(ROOT / "scripts" / "wangp_service.py")], cwd=str(ROOT), stdout=log, stderr=log, creationflags=flags)
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        status = health()
        if status.get("ready"):
            return
        if status.get("error") and "not running" not in status["error"]:
            raise WanGPUnavailable(f"WanGP session failed to start: {status['error'][:400]}")
        time.sleep(2)
    raise WanGPUnavailable("WanGP session did not become ready in time")


def list_models(**filters: Any) -> List[Dict[str, Any]]:
    query = "&".join(f"{k}={v}" for k, v in filters.items() if v)
    return _request("GET", f"/models{'?' + query if query else ''}", timeout=120)


def model_defaults(model_type: str) -> Dict[str, Any]:
    return _request("GET", f"/models/{model_type}?view=defaults", timeout=60)


def model_availability(model_type: str) -> Dict[str, Any]:
    return _request("GET", f"/models/{model_type}?view=availability", timeout=60)


def run(settings: Dict[str, Any], *, mode: str = "generate", timeout_s: float = 3600,
        progress: ProgressCallback = None) -> List[str]:
    """Submit a job and block until it finishes; returns generated file paths."""
    ensure_service()
    path = {"generate": "/generate", "postprocess": "/postprocess", "audio_remux": "/audio_remux"}[mode]
    job_id = _request("POST", path, settings)["id"]
    deadline = time.monotonic() + timeout_s
    last_status = None
    while time.monotonic() < deadline:
        job = _request("GET", f"/jobs/{job_id}?events=5", timeout=30)
        status = (job.get("phase") or "", job.get("status") or "", int(job.get("progress") or 0))
        if status != last_status and progress:
            progress(f"{status[0] or 'wangp'}: {status[1]}".strip(": "), status[2])
            last_status = status
        if job["state"] == "succeeded":
            return job["files"]
        if job["state"] == "failed":
            messages = "; ".join(e["message"] for e in job.get("errors", [])) or "unknown WanGP failure"
            tail = " | ".join(e["text"] for e in job.get("events", [])[-3:] if e.get("kind") in ("error", "stderr"))
            raise RuntimeError(f"WanGP failed: {messages}{(' [' + tail + ']') if tail else ''}")
        time.sleep(2)
    _request("POST", f"/jobs/{job_id}/cancel")
    raise TimeoutError("WanGP job timed out")


def collect(files: List[str], destination: Path, suffixes: tuple = (".mp4", ".wav", ".mp3", ".png", ".jpg")) -> Path:
    """Copy the first matching output into the Studio-managed destination path."""
    for candidate in files:
        p = Path(candidate)
        if p.suffix.lower() in suffixes and p.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, destination)
            return destination
    raise RuntimeError(f"WanGP returned no {suffixes} output among {files}")
