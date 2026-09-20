"""WanGP sidecar: keeps one warm WanGP session and exposes it over localhost HTTP.

Runs inside environments/wangp_env. Studio Core (a different Python env) talks to it
through app/core/wangp_client.py. Only one generation runs at a time; Studio Core
holds the GPU lease around every call. This product integrates WanGP (deepbeepmeep/Wan2GP).
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import traceback
import uuid
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
WANGP_ROOT = ROOT / "services" / "wangp" / "Wan2GP"
sys.path.insert(0, str(WANGP_ROOT))

_session = None
_session_error: Optional[str] = None
_jobs: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()
_run_lock = threading.Lock()


def _init_session(output_dir: Path, profile: str):
    global _session, _session_error
    try:
        from shared.api import init
        _session = init(
            root=WANGP_ROOT,
            output_dir=output_dir,
            cli_args=["--attention", "sdpa", "--profile", profile],
            console_output=True,
            console_isatty=False,
        )
        print("[wangp-service] session ready", flush=True)
    except Exception as exc:
        _session_error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-2000:]}"
        print(f"[wangp-service] session init failed: {_session_error}", flush=True)


class _Callbacks:
    def __init__(self, job: Dict[str, Any]):
        self.job = job

    def _push(self, kind: str, text: str) -> None:
        self.job["events"].append({"t": time.time(), "kind": kind, "text": text})

    def on_progress(self, p):
        self.job.update({"phase": p.phase, "status": p.status, "progress": int(p.progress or 0),
                         "step": p.current_step, "total_steps": p.total_steps})

    def on_status(self, text):
        self.job["status"] = str(text or "")
        self._push("status", str(text or ""))

    def on_stream(self, line):
        self._push(line.stream, line.text)

    def on_error(self, err):
        self._push("error", f"{err.stage}: {err.message}")


def _run_job(job_id: str) -> None:
    job = _jobs[job_id]
    with _run_lock:
        job["state"] = "running"
        job["started_at"] = time.time()
        try:
            settings = job["settings"]
            mode = job.get("mode")
            cb = _Callbacks(job)
            if mode == "postprocess":
                sj = _session.submit_media_postprocessing(settings.pop("media_source"), callbacks=cb, **settings)
            elif mode == "audio_remux":
                sj = _session.submit_audio_remux(settings.pop("video_source"), callbacks=cb, **settings)
            else:
                sj = _session.submit_task(settings, callbacks=cb)
            job["_session_job"] = sj
            result = sj.result()
            job["files"] = list(result.generated_files or [])
            job["errors"] = [{"message": e.message, "stage": e.stage} for e in (result.errors or [])]
            job["state"] = "succeeded" if result.success and job["files"] else "failed"
            if job["state"] == "failed" and not job["errors"]:
                job["errors"] = [{"message": "WanGP produced no output file", "stage": "runtime"}]
        except Exception as exc:
            job["state"] = "failed"
            job["errors"] = [{"message": f"{type(exc).__name__}: {exc}", "stage": "service"}]
            job["events"].append({"t": time.time(), "kind": "error", "text": traceback.format_exc()[-2000:]})
        finally:
            job["finished_at"] = time.time()
            job.pop("_session_job", None)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quiet
        pass

    def _json(self, code: int, payload: Any) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}") if length else {}

    def do_GET(self):
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        if url.path == "/health":
            return self._json(200, {"ready": _session is not None, "error": _session_error,
                                    "running": any(j["state"] == "running" for j in _jobs.values())})
        if _session is None:
            return self._json(503, {"error": _session_error or "session not ready"})
        if url.path == "/models":
            filters = {k: v for k, v in q.items() if k in {"family", "main_output", "inputs", "query", "model_type", "name"}}
            limit = int(q.get("limit", "0")) or None
            return self._json(200, _session.list_model_metadata(include_availability=True, limit=limit, **filters))
        if url.path.startswith("/models/"):
            model_type = url.path.split("/", 2)[2]
            view = q.get("view", "schema")
            if view == "defaults":
                return self._json(200, _session.get_default_settings(model_type))
            if view == "availability":
                return self._json(200, _session.get_model_availability(model_type))
            return self._json(200, _session.get_model_schema(model_type) or {})
        if url.path.startswith("/jobs/"):
            job = _jobs.get(url.path.split("/")[2])
            if not job:
                return self._json(404, {"error": "unknown job"})
            tail = int(q.get("events", "30"))
            view = {k: v for k, v in job.items() if k not in {"_session_job", "events", "settings"}}
            view["events"] = list(job["events"])[-tail:]
            return self._json(200, view)
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        url = urlparse(self.path)
        if _session is None:
            return self._json(503, {"error": _session_error or "session not ready"})
        if url.path in ("/generate", "/postprocess", "/audio_remux"):
            body = self._body()
            if any(j["state"] in ("queued", "running") for j in _jobs.values()):
                return self._json(409, {"error": "WanGP is busy with another job"})
            job_id = f"wj_{uuid.uuid4().hex[:10]}"
            _jobs[job_id] = {"id": job_id, "state": "queued", "progress": 0, "phase": "", "status": "", "files": [],
                             "errors": [], "events": deque(maxlen=400), "settings": body,
                             "mode": {"/generate": "generate", "/postprocess": "postprocess", "/audio_remux": "audio_remux"}[url.path],
                             "created_at": time.time()}
            threading.Thread(target=_run_job, args=(job_id,), daemon=True).start()
            return self._json(202, {"id": job_id})
        if url.path.startswith("/jobs/") and url.path.endswith("/cancel"):
            job = _jobs.get(url.path.split("/")[2])
            if not job:
                return self._json(404, {"error": "unknown job"})
            sj = job.get("_session_job")
            if sj is not None:
                sj.cancel()
            job["cancel_requested"] = True
            return self._json(200, {"ok": True})
        return self._json(404, {"error": "not found"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8199)
    parser.add_argument("--profile", default="4", help="WanGP memory profile; 4 = low VRAM")
    parser.add_argument("--output-dir", default=str(ROOT / "cache" / "wangp_outputs"))
    args = parser.parse_args()
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    (ROOT / "logs").mkdir(exist_ok=True)
    (ROOT / "logs" / "wangp_service.pid").write_text(str(__import__("os").getpid()))
    threading.Thread(target=_init_session, args=(Path(args.output_dir), args.profile), daemon=True).start()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[wangp-service] listening on http://{args.host}:{args.port} (session warming up)", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
