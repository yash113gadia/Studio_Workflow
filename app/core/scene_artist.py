"""Cinematic Scene Artist — Real FLUX Generative AI Keyframe Generation & 2.5D Motion Rendering."""
import json
import math
import os
import random
import shutil
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageFont, ImageOps

from app.core.post.ffmpeg_utils import get_ffmpeg_path, run_ffmpeg

COMFY_API_URL = "http://127.0.0.1:8188"


def get_system_font(size: int = 36) -> ImageFont.ImageFont:
    """Tries to load system font, falling back to default."""
    for font_name in ["arial.ttf", "segoeui.ttf", "calibri.ttf"]:
        try:
            return ImageFont.truetype(font_name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def generate_flux_ai_image(
    prompt_text: str,
    output_path: str,
    width: int = 480,
    height: int = 864,
    steps: int = 4,
    timeout_s: int = 1800,
    seed: Optional[int] = None,
    progress_client_id: Optional[str] = None,
) -> bool:
    """Invokes local ComfyUI API with FLUX.2 Klein 4B model to generate photorealistic AI imagery."""
    output_path = str(Path(output_path).resolve())
    workflow_template_path = Path(__file__).resolve().parents[2] / "workflows/api_format/flux_location_plate_v001.json"
    if not workflow_template_path.exists():
        return False

    with open(workflow_template_path, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    # Resolve actual registered names; mapping prefixes differ between installations.
    try:
        for node_id, kind, field, basename in [
            ("1", "UNETLoader", "unet_name", "flux-2-klein-4b-fp8.safetensors"),
            ("2", "CLIPLoader", "clip_name", "qwen_3_4b.safetensors"),
            ("3", "VAELoader", "vae_name", "flux2-vae.safetensors"),
        ]:
            with urllib.request.urlopen(f"{COMFY_API_URL}/object_info/{kind}", timeout=10) as response:
                info = json.load(response)
            names = info[kind]["input"]["required"][field][0]
            matches = [name for name in names if name.replace("\\", "/").split("/")[-1] == basename]
            if not matches:
                raise RuntimeError(f"ComfyUI cannot find {basename}")
            workflow[node_id]["inputs"][field] = matches[0]
        workflow["2"]["inputs"]["type"] = "flux2"
    except Exception as exc:
        print(f"[SceneArtist] Model lookup failed: {exc}")
        return False
    workflow["4"]["inputs"]["text"] = prompt_text
    workflow["6"]["inputs"]["width"] = width
    workflow["6"]["inputs"]["height"] = height
    workflow["9"]["inputs"]["steps"] = steps
    workflow["9"]["inputs"]["width"] = width
    workflow["9"]["inputs"]["height"] = height
    workflow["10"]["inputs"]["noise_seed"] = seed if seed is not None else random.randint(1000, 999999)

    prompt_payload = {"prompt": workflow}
    if progress_client_id:
        prompt_payload["client_id"] = progress_client_id
    payload = json.dumps(prompt_payload).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFY_API_URL}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        res = urllib.request.urlopen(req, timeout=10)
        prompt_id = json.loads(res.read())["prompt_id"]
    except Exception as exc:
        print(f"[SceneArtist] ComfyUI prompt submission failed: {exc}")
        return False

    # Poll for completion
    start_t = time.monotonic()
    while time.monotonic() - start_t < timeout_s:
        time.sleep(1.0)
        try:
            h_req = urllib.request.Request(f"{COMFY_API_URL}/history/{prompt_id}")
            h_data = json.loads(urllib.request.urlopen(h_req, timeout=5).read())
            if prompt_id in h_data:
                status = h_data[prompt_id].get("status", {})
                if status.get("status_str") == "error":
                    print(f"[SceneArtist] ComfyUI execution failed: {status.get('messages', [])}")
                    return False
                outputs = h_data[prompt_id].get("outputs", {})
                for node_id, node_out in outputs.items():
                    if "images" in node_out and node_out["images"]:
                        img_info = node_out["images"][0]
                        filename = img_info["filename"]
                        subfolder = img_info.get("subfolder", "")
                        comfy_out_dir = Path(__file__).resolve().parents[2] / "services/comfyui/ComfyUI/output"
                        src_img_path = comfy_out_dir / subfolder / filename if subfolder else comfy_out_dir / filename
                        if src_img_path.exists():
                            os.makedirs(os.path.dirname(output_path), exist_ok=True)
                            shutil.copy2(str(src_img_path), output_path)
                            print(f"[SceneArtist] FLUX image saved to {output_path}")
                            return True
        except Exception as err:
            print(f"[SceneArtist] Polling issue: {err}")

    return False


def build_ai_prompt(
    title: str,
    scene_heading: str,
    action: str,
    speaker: str,
    dialogue: Optional[str],
    genre: str,
    framing: str = "medium",
) -> str:
    """Describe the requested scene without inventing setting, costume or action."""
    framing_lower = (framing or "medium").lower()
    if "wide" in framing_lower:
        framing_desc = "Cinematic wide establishing shot"
    elif "insert" in framing_lower:
        framing_desc = "Cinematic detail insert shot"
    elif "close" in framing_lower:
        framing_desc = "Cinematic close-up shot"
    else:
        framing_desc = "Cinematic medium shot"
    parts = [framing_desc]
    if scene_heading:
        parts.append(f"Setting: {scene_heading.strip()}")
    if action:
        parts.append(f"Action: {action.strip()}")
    if speaker:
        parts.append(f"Character: {speaker.strip()}")
    if genre:
        parts.append(f"Visual tone: {genre.strip()}")
    parts.append("Photorealistic cinematography, coherent anatomy, natural detail")
    return ". ".join(parts)


def render_cinematic_keyframe(
    title: str,
    scene_heading: str,
    speaker: str,
    dialogue: Optional[str],
    genre: str,
    beat_number: int,
    output_image_path: str,
    action: str = "",
    width: int = 1080,
    height: int = 1920,
    framing: str = "medium",
    seed: Optional[int] = None,
    progress_client_id: Optional[str] = None,
) -> str:
    """Generates a high-quality vertical cinematic keyframe using local FLUX AI generation."""
    out_file = str(Path(output_image_path).resolve())
    os.makedirs(os.path.dirname(out_file), exist_ok=True)

    # 1. Attempt Real Generative AI Image Generation with FLUX
    ai_prompt = build_ai_prompt(title, scene_heading, action or "", speaker, dialogue, genre, framing=framing)
    print(f"[SceneArtist] Requesting FLUX AI generation for Beat {beat_number} ({framing}): {ai_prompt[:80]}...")

    temp_flux_png = str(Path(output_image_path).with_suffix(".flux.png"))
    ai_success = generate_flux_ai_image(
        prompt_text=ai_prompt,
        output_path=temp_flux_png,
        width=768 if width <= height else 1344,
        height=1344 if width < height else 768,
        steps=4,
        timeout_s=1800,
        seed=seed,
        progress_client_id=progress_client_id,
    )

    if ai_success and os.path.exists(temp_flux_png):
        try:
            # Scale to clean target resolution (1080x1920) without any text or letterbox degradation
            ai_img = Image.open(temp_flux_png).convert("RGB")
            if (ai_img.width, ai_img.height) != (width, height):
                ai_img = ImageOps.fit(ai_img, (width, height), method=Image.Resampling.LANCZOS)

            ai_img.save(out_file, "JPEG", quality=95)
            try:
                os.remove(temp_flux_png)
            except Exception:
                pass
            return out_file
        except Exception as exc:
            print(f"[SceneArtist] Processing AI image failed: {exc}")

    raise RuntimeError(
        f"FLUX keyframe generation failed for beat {beat_number}. "
        "Check the local ComfyUI server, model availability and execution log."
    )


def render_shot_video_clip(
    image_path: str,
    output_mp4_path: str,
    duration_s: float = 4.0,
    beat_number: int = 1,
    fps: int = 24,
    width: int = 1080,
    height: int = 1920,
    framing: str = "medium",
    genre: str = "cyberpunk",
    motion: str = "push_in",
) -> bool:
    """Animate a still with a camera move (push/pull/pan/static); this is not generated motion."""
    if width <= 0 or height <= 0 or width % 2 or height % 2 or fps <= 0:
        raise ValueError("Video dimensions must be positive and even; fps must be positive")
    if not math.isfinite(duration_s) or duration_s <= 0:
        raise ValueError("Video duration must be positive and finite")
    out_file = str(Path(output_mp4_path).resolve())
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    total_frames = max(1, round(duration_s * fps))
    n = max(1, total_frames - 1)
    centered = "x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2'"
    zoompan = {
        "push_in": f"z='1+0.04*on/{n}':{centered}",
        "pull_out": f"z='1.04-0.04*on/{n}':{centered}",
        "pan_left": f"z='1.06':x='(iw-iw/zoom)*(1-on/{n})':y='ih/2-ih/zoom/2'",
        "pan_right": f"z='1.06':x='(iw-iw/zoom)*on/{n}':y='ih/2-ih/zoom/2'",
        "tilt_up": f"z='1.06':x='iw/2-iw/zoom/2':y='(ih-ih/zoom)*(1-on/{n})'",
        "tilt_down": f"z='1.06':x='iw/2-iw/zoom/2':y='(ih-ih/zoom)*on/{n}'",
        "static": f"z='1':{centered}",
    }.get(motion, f"z='1+0.04*on/{n}':{centered}")
    # Supersample before zoompan to reduce integer-crop jitter. Crop preserves
    # aspect ratio; no weather or exposure effects are added to the source.
    work_w, work_h = width * 2, height * 2
    filters = (
        f"scale={work_w}:{work_h}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={work_w}:{work_h},setsar=1,"
        f"zoompan={zoompan}:"
        f"s={width}x{height}:fps={fps}:d={total_frames}"
    )
    cmd = [
        "-y", "-i", str(Path(image_path).resolve()),
        "-vf", filters, "-frames:v", str(total_frames),
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_file,
    ]
    ret, _, err = run_ffmpeg(cmd, timeout_s=max(180, int(duration_s * 60)))
    if ret != 0:
        raise RuntimeError(f"Still animation encoding failed: {err[-2000:]}")
    return os.path.exists(out_file) and os.path.getsize(out_file) > 1000
