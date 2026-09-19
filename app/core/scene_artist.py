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
from PIL import Image, ImageDraw, ImageFont, ImageFilter

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
    timeout_s: int = 60,
) -> bool:
    """Invokes local ComfyUI API with FLUX.2 Klein 4B model to generate photorealistic AI imagery."""
    output_path = str(Path(output_path).resolve())
    workflow_template_path = Path("workflows/api_format/flux_location_plate_v001.json").resolve()
    if not workflow_template_path.exists():
        return False

    with open(workflow_template_path, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    # Configure exact model paths and prompt parameters for ComfyUI
    workflow["1"]["inputs"]["unet_name"] = r"diffusion_models\flux-2-klein-4b-fp8.safetensors"
    workflow["2"]["inputs"]["clip_name"] = r"text_encoders\qwen_3_4b.safetensors"
    workflow["2"]["inputs"]["type"] = "flux2"
    workflow["3"]["inputs"]["vae_name"] = r"vae\flux2-vae.safetensors"
    workflow["4"]["inputs"]["text"] = prompt_text
    workflow["6"]["inputs"]["width"] = width
    workflow["6"]["inputs"]["height"] = height
    workflow["9"]["inputs"]["steps"] = steps
    workflow["9"]["inputs"]["width"] = width
    workflow["9"]["inputs"]["height"] = height
    workflow["10"]["inputs"]["noise_seed"] = random.randint(1000, 999999)

    payload = json.dumps({"prompt": workflow}).encode("utf-8")
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
    start_t = time.time()
    while time.time() - start_t < timeout_s:
        time.sleep(1.0)
        try:
            h_req = urllib.request.Request(f"{COMFY_API_URL}/history/{prompt_id}")
            h_data = json.loads(urllib.request.urlopen(h_req, timeout=5).read())
            if prompt_id in h_data:
                outputs = h_data[prompt_id].get("outputs", {})
                for node_id, node_out in outputs.items():
                    if "images" in node_out and node_out["images"]:
                        img_info = node_out["images"][0]
                        filename = img_info["filename"]
                        subfolder = img_info.get("subfolder", "")
                        comfy_out_dir = Path("services/comfyui/ComfyUI/output").resolve()
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
) -> str:
    """Constructs a descriptive, photorealistic cinematic prompt for FLUX diffusion."""
    genre_lower = (genre or "cyberpunk").lower()
    
    clean_heading = scene_heading.replace("SCENE", "").replace("EXT.", "").replace("INT.", "").replace("-", ",").strip()
    action_text = (action or "").strip()
    if len(action_text) > 160:
        action_text = action_text[:160]

    if "cyber" in genre_lower:
        base = "cinematic photorealistic Neo-Mumbai cyberpunk alley street at night, neon reflections on wet asphalt, holographic displays"
    elif "romance" in genre_lower:
        base = "cinematic photorealistic cozy monsoon cafe in evening, warm amber glass, rain drops on windows, soft warm bokeh"
    elif "mystery" in genre_lower:
        base = "cinematic photorealistic vintage archive room, shaft of moonlight cutting through dust motes, old wooden library shelves, antique brass safe"
    else:
        base = "cinematic photorealistic deep space observatory deck, nebula starlight outside viewing dome, glowing telemetry monitors"

    character_desc = f"{speaker} protagonist" if speaker else "lone character"
    full_prompt = f"{base}, {clean_heading}, {action_text}, {character_desc}, dramatic cinematic lighting, shallow depth of field, photorealistic 8k masterpiece"
    return full_prompt


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
) -> str:
    """Generates a high-quality vertical cinematic keyframe using local FLUX AI generation."""
    out_file = str(Path(output_image_path).resolve())
    os.makedirs(os.path.dirname(out_file), exist_ok=True)

    # 1. Attempt Real Generative AI Image Generation with FLUX
    ai_prompt = build_ai_prompt(title, scene_heading, action or dialogue or "", speaker, dialogue, genre)
    print(f"[SceneArtist] Requesting FLUX AI generation for Beat {beat_number}: {ai_prompt[:80]}...")
    
    temp_flux_png = str(Path(output_image_path).with_suffix(".flux.png"))
    ai_success = generate_flux_ai_image(
        prompt_text=ai_prompt,
        output_path=temp_flux_png,
        width=480,
        height=864,
        steps=4,
        timeout_s=45,
    )

    if ai_success and os.path.exists(temp_flux_png):
        try:
            # Load and upscale/scale the AI generated image to target resolution
            ai_img = Image.open(temp_flux_png).convert("RGB")
            ai_img = ai_img.resize((width, height), Image.Resampling.LANCZOS)
            
            # Add subtle, high-end cinematic letterboxing and typography
            draw = ImageDraw.Draw(ai_img)
            bar_height = 140
            
            # Sleek translucent letterboxing bars
            top_bar = Image.new("RGBA", (width, bar_height), (0, 0, 0, 180))
            bottom_bar = Image.new("RGBA", (width, bar_height), (0, 0, 0, 180))
            
            ai_rgba = ai_img.convert("RGBA")
            ai_rgba.paste(top_bar, (0, 0), top_bar)
            ai_rgba.paste(bottom_bar, (0, height - bar_height), bottom_bar)
            ai_img = ai_rgba.convert("RGB")
            draw = ImageDraw.Draw(ai_img)

            # Typography
            font_title = get_system_font(24)
            font_meta = get_system_font(20)
            
            draw.text((40, 35), "PREETI STUDIO • FLUX.2 AI CINEMA", fill=(148, 163, 184), font=font_meta)
            draw.text((40, 70), f"{title.upper()} — SCENE {beat_number:02d}", fill=(255, 255, 255), font=font_title)
            
            if speaker:
                draw.text((40, height - 90), f"🎭 {speaker.upper()}", fill=(6, 182, 212), font=font_title)

            ai_img.save(out_file, "JPEG", quality=95)
            try:
                os.remove(temp_flux_png)
            except Exception:
                pass
            return out_file
        except Exception as exc:
            print(f"[SceneArtist] Processing AI image failed: {exc}")

    # 2. Fallback: Atmospheric gradient canvas if AI server is busy
    print("[SceneArtist] Using gradient canvas fallback")
    genre_lower = (genre or "cyberpunk").lower()
    bg_col = (8, 10, 22) if "cyber" in genre_lower else ((24, 15, 12) if "romance" in genre_lower else (12, 13, 16))
    img = Image.new("RGB", (width, height), bg_col)
    draw = ImageDraw.Draw(img)
    font_mid = get_system_font(36)
    draw.text((80, height // 2 - 40), title.upper(), fill=(255, 255, 255), font=font_mid)
    draw.text((80, height // 2 + 20), f"SCENE {beat_number:02d} • {genre.upper()}", fill=(148, 163, 184), font=get_system_font(24))
    img.save(out_file, "JPEG", quality=90)
    return out_file


def render_shot_video_clip(
    image_path: str,
    output_mp4_path: str,
    duration_s: float = 4.0,
    beat_number: int = 1,
    fps: int = 24,
    width: int = 1080,
    height: int = 1920,
) -> bool:
    """Renders a dynamic 2.5D camera motion MP4 clip from a photorealistic keyframe image using FFmpeg."""
    out_file = str(Path(output_mp4_path).resolve())
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    dur = max(1.0, round(duration_s, 2))
    total_frames = int(dur * fps)

    # Alternating smooth cinematic camera movements
    motion_idx = beat_number % 3
    if motion_idx == 1:
        # Slow cinematic push-in towards center
        zoom_expr = f"zoompan=z='min(zoom+0.0006,1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}:d={total_frames}"
    elif motion_idx == 2:
        # Slow cinematic pan
        zoom_expr = f"zoompan=z='1.06':x='if(lte(on,1),(iw-iw/zoom),max(0,x-0.5))':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}:d={total_frames}"
    else:
        # Slow cinematic pull-out
        zoom_expr = f"zoompan=z='if(lte(zoom,1.0),1.08,max(1.001,zoom-0.0004))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}:d={total_frames}"

    cmd = [
        "-y",
        "-loop", "1",
        "-i", str(Path(image_path).resolve()),
        "-vf", zoom_expr,
        "-t", str(dur),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        out_file,
    ]
    ret, _, _ = run_ffmpeg(cmd, timeout_s=60)
    return ret == 0 and os.path.exists(out_file) and os.path.getsize(out_file) > 1000
