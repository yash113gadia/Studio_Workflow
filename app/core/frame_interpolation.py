"""Real FILM 2x frame interpolation through ComfyUI core nodes."""
import json
import shutil
import time
import uuid
from pathlib import Path

from app.core.local_video import ROOT, request


def interpolate_video_2x(source_path: str, output_path: str, timeout_s: int = 1800, client_id: str | None = None) -> bool:
    source = Path(source_path).resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    model_name = "film_net_fp16.safetensors"
    names = request("/object_info/FrameInterpolationModelLoader")["FrameInterpolationModelLoader"]["input"]["required"]["model_name"][1]["options"]
    if model_name not in names:
        raise RuntimeError("FILM interpolation model is not visible to ComfyUI")

    input_dir = ROOT / "services/comfyui/ComfyUI/input"
    output_dir = ROOT / "services/comfyui/ComfyUI/output"
    staged_name = f"studio_film_{uuid.uuid4().hex}{source.suffix}"
    staged = input_dir / staged_name
    prefix = f"studio_film/{uuid.uuid4().hex}"
    shutil.copy2(source, staged)
    workflow = {
        "1": {"class_type": "LoadVideo", "inputs": {"file": staged_name}},
        "2": {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
        "3": {"class_type": "FrameInterpolationModelLoader", "inputs": {"model_name": model_name}},
        "4": {"class_type": "FrameInterpolate", "inputs": {"interp_model": ["3", 0], "images": ["2", 0], "multiplier": 2}},
        "7": {"class_type": "ComfyMathExpression", "inputs": {"expression": "a * 2", "values.a": ["2", 2]}},
        "5": {"class_type": "CreateVideo", "inputs": {
            "images": ["4", 0], "audio": ["2", 1], "fps": ["7", 0],
            "bit_depth": 8, "color_space": "sRGB", "codec": "h264",
        }},
        "6": {"class_type": "SaveVideo", "inputs": {
            "video": ["5", 0], "filename_prefix": prefix, "format": "mp4", "codec": "h264",
        }},
    }
    payload = {"prompt": workflow}
    if client_id:
        payload["client_id"] = client_id
    try:
        prompt_id = request("/prompt", payload)["prompt_id"]
        deadline = time.monotonic() + timeout_s
        rendered = None
        while time.monotonic() < deadline:
            history = request(f"/history/{prompt_id}").get(prompt_id)
            if history:
                if history.get("status", {}).get("status_str") == "error":
                    raise RuntimeError(f"FILM interpolation failed: {history.get('status', {}).get('messages', [])}")
                for node_output in history.get("outputs", {}).values():
                    for key in ("videos", "gifs", "images"):
                        for item in node_output.get(key, []):
                            candidate = output_dir / item.get("subfolder", "") / item["filename"]
                            if candidate.suffix.lower() in {".mp4", ".webm", ".mkv"} and candidate.exists():
                                rendered = candidate
                if rendered:
                    break
            time.sleep(1)
        if not rendered:
            raise TimeoutError("FILM interpolation did not return a video")
        destination = Path(output_path).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(rendered, destination)
        destination.with_suffix(".interpolation.json").write_text(json.dumps({
            "engine": "FILM FP16", "multiplier": 2, "source": str(source), "output": str(destination)
        }, indent=2), encoding="utf-8")
        return destination.exists() and destination.stat().st_size > 1000
    finally:
        staged.unlink(missing_ok=True)
