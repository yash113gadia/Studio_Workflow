"""
Preeti Studio — Post-install smoke test
Proves this PC can run the verified Creator path: Studio Core and ComfyUI are up,
ComfyUI is on the NVIDIA GPU, and the app's own code renders a FLUX keyframe, a short
LTX motion clip from it, and a Windows voice line. Outputs go to temp/smoke_test.
Run with Studio Core and ComfyUI already started (scripts/start_comfy.ps1, scripts/start_studio.ps1).
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.audio.speech_synth import synthesize_speech  # noqa: E402
from app.core.local_video import render_ltx_video  # noqa: E402
from app.core.post.ffmpeg_utils import get_ffmpeg_path, run_ffmpeg  # noqa: E402
from app.core.scene_artist import generate_flux_ai_image  # noqa: E402

OUT_DIR = ROOT / "temp" / "smoke_test"
PROMPT = "A farmer standing in a golden wheat field at sunset, cinematic photograph, natural light"


def get_json(url: str, timeout: int = 10) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.load(response)


def wait_for_json(url: str, timeout_s: int = 180) -> dict:
    """Services can take a few minutes to come up the first time; poll instead of failing at once."""
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            return get_json(url)
        except Exception:
            if time.monotonic() > deadline:
                raise RuntimeError(f"no response from {url} after {timeout_s}s; see the logs folder")
            time.sleep(3)


def check_studio_core() -> str:
    health = wait_for_json("http://127.0.0.1:8000/api/v1/health")
    if health.get("status") != "ok":
        raise RuntimeError(f"health status is {health.get('status')!r}")
    return f"free disk {health.get('free_disk_gb')} GB"


def check_comfy_gpu() -> str:
    devices = wait_for_json("http://127.0.0.1:8188/system_stats").get("devices", [])
    if not devices or devices[0].get("type") != "cuda":
        raise RuntimeError(f"ComfyUI is not using an NVIDIA CUDA device: {devices}")
    return f"{devices[0]['name']}, {devices[0]['vram_total'] / 1024**3:.1f} GB VRAM"


def check_ffmpeg() -> str:
    code, out, err = run_ffmpeg(["-hide_banner", "-version"], timeout_s=30)
    if code != 0:
        raise RuntimeError(err[-300:] or f"exit code {code}")
    return f"{get_ffmpeg_path()} ({out.splitlines()[0]})"


def check_voice() -> str:
    path = OUT_DIR / "voice.wav"
    if not synthesize_speech("Preeti Studio is ready.", str(path)):
        raise RuntimeError("Windows speech synthesis produced no audio")
    return str(path)


def check_flux() -> str:
    path = OUT_DIR / "flux_keyframe.png"
    path.unlink(missing_ok=True)
    if not generate_flux_ai_image(PROMPT, str(path), width=480, height=864, steps=4, seed=42) or not path.exists():
        raise RuntimeError("FLUX did not produce an image; see logs/comfyui_err.log")
    return str(path)


def check_ltx() -> str:
    path = OUT_DIR / "ltx_motion.mp4"
    path.unlink(missing_ok=True)
    ok = render_ltx_video(
        OUT_DIR / "flux_keyframe.png", path,
        "The farmer slowly turns his head and the wheat sways in the wind.",
        duration=2, quality_profile="draft",
    )
    if not ok:
        raise RuntimeError("LTX did not produce a video; see logs/comfyui_err.log")
    return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-ltx", action="store_true", help="skip the slower LTX motion render")
    args = parser.parse_args()
    sys.stdout.reconfigure(errors="replace")  # cp1252 consoles cannot print every GPU or path name
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    checks = [
        ("Studio Core API on :8000", check_studio_core),
        ("ComfyUI on the NVIDIA GPU", check_comfy_gpu),
        ("FFmpeg", check_ffmpeg),
        ("Windows voice", check_voice),
        ("FLUX.2 Klein keyframe (first run loads ~12 GB of models, can take minutes)", check_flux),
    ]
    if not args.skip_ltx:
        checks.append(("LTX-Video 2-second motion clip (draft quality)", check_ltx))

    failed = []
    for name, check in checks:
        if name.startswith("LTX") and any(f.startswith("FLUX") for f in failed):
            print(f"[SKIP] {name}: needs the FLUX keyframe")
            failed.append(name)
            continue
        print(f"... {name}", flush=True)
        started = time.time()
        try:
            detail = check()
            print(f"[PASS] {name} ({time.time() - started:.0f}s): {detail}", flush=True)
        except Exception as exc:
            print(f"[FAIL] {name}: {exc}", flush=True)
            failed.append(name)

    print()
    if failed:
        print(f"SMOKE TEST FAILED: {len(failed)} of {len(checks)} checks did not pass.")
        return 1
    print(f"SMOKE TEST PASSED: all {len(checks)} checks. Results are in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
