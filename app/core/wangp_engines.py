"""Studio capability adapters backed by the WanGP sidecar (H3 video, Chatterbox voice, ACE-Step music).

Each function maps a Studio request onto WanGP task settings, runs it, and copies the
output into a Studio-managed path. WanGP downloads any model files it is missing on
first use, so the first call of each engine is slow.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional

from app.core import wangp_client as wg

Progress = Optional[Callable[[str, int], None]]

H3_MODEL = "minimax_h3_fl2va_pruned"
H3_FPS = 24
H3_MIN_FRAMES, H3_FRAME_STEP = 107, 17
H3_RESOLUTIONS = {"9:16": "480x832", "16:9": "832x480", "1:1": "640x640"}


def _h3_frames(duration_s: float) -> int:
    target = int(round(duration_s * H3_FPS))
    frames = H3_MIN_FRAMES
    while frames < target:
        frames += H3_FRAME_STEP
    return frames


def render_h3_i2v(image_path: str, output_path: str, prompt: str, duration_s: float, aspect_ratio: str = "9:16",
                  seed: int = 42, steps: int = 20, progress: Progress = None) -> bool:
    settings = {
        "model_type": H3_MODEL,
        "prompt": prompt,
        "image_prompt_type": "S",
        "image_start": [str(Path(image_path).resolve())],
        "resolution": H3_RESOLUTIONS.get(aspect_ratio, "480x832"),
        "video_length": _h3_frames(duration_s),
        "num_inference_steps": steps,
        "seed": seed,
        "force_fps": H3_FPS,
    }
    files = wg.run(settings, timeout_s=5400, progress=progress)
    wg.collect(files, Path(output_path), (".mp4",))
    return True


def synthesize_chatterbox(text: str, output_wav: str, language: str = "en", voice_sample: Optional[str] = None,
                          seed: int = 7, exaggeration: float = 0.5, pace: float = 0.5, progress: Progress = None) -> bool:
    settings: Dict = {
        "model_type": "chatterbox",
        "prompt": text.strip(),
        "model_mode": language,
        "seed": seed,
        "audio_prompt_type": "A" if voice_sample else "",
        "custom_settings": {"exaggeration": exaggeration, "pace": pace},
    }
    if voice_sample:
        settings["audio_guide"] = str(Path(voice_sample).resolve())
    files = wg.run(settings, timeout_s=1800, progress=progress)
    wg.collect(files, Path(output_wav), (".wav", ".mp3", ".flac"))
    return True


def generate_ace_step_music(description: str, duration_s: float, output_path: str, lyrics: str = "", seed: int = 42,
                            progress: Progress = None) -> bool:
    settings = {
        "model_type": "ace_step_v1_5",
        "prompt": lyrics or "[Instrumental]",
        "alt_prompt": description,
        "duration_seconds": max(10, int(round(duration_s))),
        "num_inference_steps": 8,
        "seed": seed,
        "audio_prompt_type": "",
    }
    files = wg.run(settings, timeout_s=3600, progress=progress)
    wg.collect(files, Path(output_path), (".wav", ".mp3", ".flac"))
    return True


_status_cache: Dict[str, object] = {"at": 0.0, "value": None}


def engine_status() -> Dict[str, Dict]:
    """Live availability of WanGP-backed engines: needs the sidecar up; model files may still auto-download."""
    import time
    if _status_cache["value"] is not None and time.monotonic() - float(_status_cache["at"]) < 60:
        return _status_cache["value"]  # type: ignore[return-value]
    health = wg.health()
    if not health.get("ready"):
        note = "WanGP sidecar not running." if "not running" in (health.get("error") or "") else f"WanGP: {(health.get('error') or 'starting')[:120]}"
        return {k: {"available": False, "note": note} for k in ("h3", "chatterbox", "ace_step")}
    busy = bool(health.get("running"))
    out = {}
    for key, model in (("h3", H3_MODEL), ("chatterbox", "chatterbox"), ("ace_step", "ace_step_v1_5")):
        if busy:
            out[key] = {"available": True, "note": "WanGP is busy with a job; missing files download automatically on first use."}
            continue
        try:
            avail = wg._request("GET", f"/models/{model}?view=availability", timeout=8)
            status = avail.get("status", "unknown")
            out[key] = {"available": True, "note": "Model files present." if avail.get("available") else f"WanGP will download missing files on first use (status: {status})."}
        except Exception as exc:
            out[key] = {"available": True, "note": f"WanGP reachable; availability check deferred ({str(exc)[:80]})."}
    _status_cache.update({"at": time.monotonic(), "value": out})
    return out
