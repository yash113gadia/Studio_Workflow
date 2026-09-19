"""Cinematic Scene Artist — Visual Keyframe Generation & 2.5D Camera Motion Rendering."""
import math
import os
import random
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from app.core.post.ffmpeg_utils import get_ffmpeg_path, run_ffmpeg


def get_system_font(size: int = 36) -> ImageFont.ImageFont:
    """Tries to load system font, falling back to default."""
    for font_name in ["arial.ttf", "segoeui.ttf", "calibri.ttf"]:
        try:
            return ImageFont.truetype(font_name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def render_cinematic_keyframe(
    title: str,
    scene_heading: str,
    speaker: str,
    dialogue: Optional[str],
    genre: str,
    beat_number: int,
    output_image_path: str,
    width: int = 1080,
    height: int = 1920,
) -> str:
    """Generates a high-quality vertical cinematic keyframe matching the genre aesthetic."""
    out_file = str(Path(output_image_path).resolve())
    os.makedirs(os.path.dirname(out_file), exist_ok=True)

    genre_lower = (genre or "cyberpunk").lower()

    # Define genre color palettes (Background, Primary Glow, Secondary Glow, Accent)
    if "cyber" in genre_lower:
        bg_col = (8, 10, 22)
        glow1 = (139, 92, 246)   # Purple
        glow2 = (6, 182, 212)    # Cyan
        accent = (244, 63, 94)   # Neon pink
        genre_label = "CYBERPUNK NOIR"
    elif "romance" in genre_lower:
        bg_col = (24, 15, 12)
        glow1 = (245, 158, 11)   # Warm amber
        glow2 = (239, 68, 68)    # Crimson red
        accent = (254, 215, 170) # Golden peach
        genre_label = "MONSOON ROMANCE"
    elif "mystery" in genre_lower:
        bg_col = (12, 13, 16)
        glow1 = (71, 85, 105)    # Slate
        glow2 = (217, 119, 6)    # Amber bronze
        accent = (226, 232, 240) # Moonlight white
        genre_label = "ARCHIVAL MYSTERY"
    else:  # Sci-fi / default
        bg_col = (4, 7, 20)
        glow1 = (59, 130, 246)   # Deep blue
        glow2 = (147, 51, 234)   # Violet nebula
        accent = (56, 189, 248)  # Starlight cyan
        genre_label = "DEEP SPACE SCI-FI"

    # Base canvas
    img = Image.new("RGB", (width, height), bg_col)
    draw = ImageDraw.Draw(img)

    # 1. Background atmospheric lighting & nebula/bokeh circles
    random.seed(beat_number * 100 + len(scene_heading))
    for _ in range(8):
        bx = random.randint(100, width - 100)
        by = random.randint(300, height - 500)
        br = random.randint(180, 420)
        col = random.choice([glow1, glow2, accent])
        # Draw translucent layered bokeh
        faded_col = (int(col[0] * 0.25), int(col[1] * 0.25), int(col[2] * 0.25))
        draw.ellipse([(bx - br, by - br), (bx + br, by + br)], fill=faded_col)

    # Center cinematic atmospheric circle
    draw.ellipse([(200, 500), (880, 1180)], fill=(int(glow1[0] * 0.4), int(glow1[1] * 0.4), int(glow1[2] * 0.4)))
    draw.ellipse([(320, 620), (760, 1060)], fill=(int(glow2[0] * 0.5), int(glow2[1] * 0.5), int(glow2[2] * 0.5)))

    # 2. Cinematic character silhouette in the center
    char_silhouette = (10, 12, 18)
    head_y = 650 + (beat_number % 2) * 20
    draw.ellipse([(450, head_y), (630, head_y + 180)], fill=char_silhouette)  # Head
    # Shoulders & torso
    draw.polygon([
        (340, 1300),
        (430, head_y + 180),
        (650, head_y + 180),
        (740, 1300),
    ], fill=char_silhouette)

    # 3. Top & Bottom letterbox bars for high-end cinematic feel
    bar_height = 200
    draw.rectangle([(0, 0), (width, bar_height)], fill=(0, 0, 0))
    draw.rectangle([(0, height - bar_height - 60), (width, height)], fill=(0, 0, 0))

    # Decorative accent lines
    draw.line([(0, bar_height), (width, bar_height)], fill=glow2, width=3)
    draw.line([(0, height - bar_height - 60), (width, height - bar_height - 60)], fill=glow1, width=3)

    # 4. Typography & Watermarks
    font_small = get_system_font(26)
    font_mid = get_system_font(34)
    font_big = get_system_font(46)
    font_label = get_system_font(22)

    # Brand & Genre Tag (Top Bar)
    draw.text((60, 50), "PREETI STUDIO — LOCAL AI OS", fill=(148, 163, 184), font=font_label)
    draw.text((60, 85), f"▶ {genre_label.upper()} • BEAT {beat_number:02d}", fill=accent, font=font_mid)
    draw.text((60, 135), f"{title.upper()}", fill=(255, 255, 255), font=font_small)

    # Scene Heading (Floating lower third)
    clean_heading = scene_heading.replace("SCENE", "ACT").strip()
    draw.text((60, height - bar_height - 130), clean_heading[:45].upper(), fill=(203, 213, 225), font=font_small)

    # Speaker Indicator (Above subtitles)
    if speaker:
        draw.text((60, height - bar_height - 20), f"🎭 {speaker.upper()}", fill=accent, font=font_mid)

    # Save final image
    img.save(out_file, "JPEG", quality=95)
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
    """Renders a dynamic 2.5D camera motion MP4 clip from a keyframe image using FFmpeg."""
    out_file = str(Path(output_mp4_path).resolve())
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    dur = max(1.0, round(duration_s, 2))
    total_frames = int(dur * fps)

    # Alternating cinematic camera motions
    motion_idx = beat_number % 3
    if motion_idx == 1:
        # Slow push-in towards center
        zoom_expr = f"zoompan=z='min(zoom+0.0006,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}:d={total_frames}"
    elif motion_idx == 2:
        # Slow pan left
        zoom_expr = f"zoompan=z='1.08':x='if(lte(on,1),(iw-iw/zoom),max(0,x-0.6))':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}:d={total_frames}"
    else:
        # Slow pull-out
        zoom_expr = f"zoompan=z='if(lte(zoom,1.0),1.10,max(1.001,zoom-0.0005))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}:d={total_frames}"

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
