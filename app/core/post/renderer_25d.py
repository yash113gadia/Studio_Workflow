"""2.5D Cheap-Shot Renderer — Parallax, Depth Layering, and Camera Motion Engine."""
import json
import math
import os
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, Field

from app.core.post.ffmpeg_utils import get_ffmpeg_path, run_ffmpeg


class Motion25DType(str, Enum):
    PUSH_IN = "push_in"
    PULL_OUT = "pull_out"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"
    PARALLAX = "parallax"
    STATIC_SUBTLE = "static_subtle"


class OverlayEffectType(str, Enum):
    NONE = "none"
    PARTICLE_DUST = "particle_dust"
    LIGHT_LEAK = "light_leak"
    FOG_MIST = "fog_mist"


class Render25DRequest(BaseModel):
    project_id: str
    image_path: str
    duration_s: float = 3.0
    fps: int = 24
    width: int = 480
    height: int = 864
    motion_type: Motion25DType = Motion25DType.PUSH_IN
    overlay_effect: OverlayEffectType = OverlayEffectType.NONE
    depth_parallax: bool = False
    shot_id: Optional[str] = None
    output_path: Optional[str] = None


class Render25DResponse(BaseModel):
    job_id: str
    output_video_path: str
    duration_s: float
    fps: int
    resolution: str
    motion_type: str
    overlay_effect: str
    parallax_enabled: bool
    diffusion_cost: float = 0.0
    render_time_ms: int
    provenance_json: Dict[str, Any] = Field(default_factory=dict)


class Renderer25DError(Exception):
    """Exception raised during 2.5D rendering."""
    pass


class Renderer25D:
    """Lightweight 2.5D cheap-shot engine for camera motion, parallax,

    and subtle atmospheric overlays with zero diffusion inference cost.
    """

    @classmethod
    def build_video_filter(
        cls,
        motion: Motion25DType,
        overlay: OverlayEffectType,
        duration_s: float,
        fps: int,
        width: int,
        height: int,
        parallax: bool = False,
    ) -> str:
        """Builds the FFmpeg complex filtergraph for camera movement and overlays."""
        total_frames = max(1, int(duration_s * fps))

        # Base camera motion filters
        if motion == Motion25DType.PUSH_IN:
            # Slow push-in towards center (from 1.0 to 1.15)
            cam_expr = (
                f"zoompan=z='min(zoom+0.0008,1.15)':d={total_frames}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}"
            )
        elif motion == Motion25DType.PULL_OUT:
            # Slow pull-out from 1.15 to 1.0
            cam_expr = (
                f"zoompan=z='if(lte(zoom,1.0),1.15,max(1.001,zoom-0.0008))':d={total_frames}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}"
            )
        elif motion == Motion25DType.PAN_LEFT:
            # Slow horizontal pan left
            cam_expr = (
                f"zoompan=z='1.12':x='if(lte(on,1),(iw-iw/zoom),max(0,x-0.8))':"
                f"y='ih/2-(ih/zoom/2)':d={total_frames}:s={width}x{height}:fps={fps}"
            )
        elif motion == Motion25DType.PAN_RIGHT:
            # Slow horizontal pan right
            cam_expr = (
                f"zoompan=z='1.12':x='if(lte(on,1),0,min((iw-iw/zoom),x+0.8))':"
                f"y='ih/2-(ih/zoom/2)':d={total_frames}:s={width}x{height}:fps={fps}"
            )
        elif motion == Motion25DType.PARALLAX or parallax:
            # Parallax mode: foreground zooms faster while shifting offset
            cam_expr = (
                f"zoompan=z='min(zoom+0.0012,1.20)':d={total_frames}:"
                f"x='iw/2-(iw/zoom/2)+sin(on*0.02)*10':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}"
            )
        else:  # STATIC_SUBTLE
            cam_expr = (
                f"zoompan=z='1.02':d={total_frames}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}"
            )

        filter_chain = [cam_expr]

        # Atmospheric overlays
        if overlay == OverlayEffectType.PARTICLE_DUST:
            # Floating micro-noise overlay simulating cinematic dust motes
            filter_chain.append("noise=alls=12:allf=t+u")
        elif overlay == OverlayEffectType.LIGHT_LEAK:
            # Subtle warm golden curves tint
            filter_chain.append("curves=r='0/0 0.5/0.55 1/1':b='0/0 0.5/0.46 1/0.95'")
        elif overlay == OverlayEffectType.FOG_MIST:
            # Soft diffusing contrast reduction with slight cool tint
            filter_chain.append("eq=contrast=0.92:brightness=0.04:saturation=0.95")

        filter_chain.append(f"scale={width}:{height}")
        return ",".join(filter_chain)

    @classmethod
    def render(
        cls,
        req: Render25DRequest,
        mock_mode: bool = False,
    ) -> Render25DResponse:
        """Renders a 2.5D shot from a still image with camera motion and optional atmospheric overlay."""
        t0 = time.time()
        job_id = f"job_25d_{uuid.uuid4().hex[:12]}"

        # Validate input image
        input_path = Path(req.image_path).resolve()
        if not input_path.exists():
            raise Renderer25DError(f"Input image does not exist: {req.image_path}")

        # Determine output path
        if req.output_path:
            out_file = Path(req.output_path).resolve()
        else:
            shot_label = req.shot_id or f"shot_{uuid.uuid4().hex[:8]}"
            out_dir = Path(os.path.join(os.getcwd(), "projects", req.project_id, "renders", "2_5d")).resolve()
            os.makedirs(out_dir, exist_ok=True)
            out_file = out_dir / f"render25d_{shot_label}_{req.motion_type.value}.mp4"

        os.makedirs(out_file.parent, exist_ok=True)

        if mock_mode:
            # Fast mock generation for unit tests
            with open(out_file, "wb") as f:
                f.write(b"\x00\x00\x00 ftypisom\x00\x00\x02\x00isomiso2avc1mp41")
                f.write(b"PREETI_STUDIO_25D_RENDERER_OUTPUT_DATA" * 50)
            elapsed_ms = int((time.time() - t0) * 1000)
        else:
            vf = cls.build_video_filter(
                motion=req.motion_type,
                overlay=req.overlay_effect,
                duration_s=req.duration_s,
                fps=req.fps,
                width=req.width,
                height=req.height,
                parallax=req.depth_parallax,
            )

            # Build FFmpeg command: loop image for exact duration, apply zoompan filter, encode x264
            cmd = [
                "-loop", "1",
                "-i", str(input_path),
                "-vf", vf,
                "-t", str(req.duration_s),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-r", str(req.fps),
                "-y", str(out_file),
            ]

            code, stdout, stderr = run_ffmpeg(cmd, timeout_s=60)
            if code != 0:
                raise Renderer25DError(f"FFmpeg 2.5D render failed (exit code {code}): {stderr}")

            elapsed_ms = int((time.time() - t0) * 1000)

        provenance = {
            "engine": "preeti_studio_2.5d_renderer",
            "section_ref": "Master Plan Section 43 & Phase 14",
            "source_image": str(input_path),
            "duration_s": req.duration_s,
            "fps": req.fps,
            "resolution": f"{req.width}x{req.height}",
            "motion_type": req.motion_type.value,
            "overlay_effect": req.overlay_effect.value,
            "depth_parallax": req.depth_parallax,
            "diffusion_cost": 0.0,
            "render_time_ms": elapsed_ms,
        }

        return Render25DResponse(
            job_id=job_id,
            output_video_path=str(out_file),
            duration_s=req.duration_s,
            fps=req.fps,
            resolution=f"{req.width}x{req.height}",
            motion_type=req.motion_type.value,
            overlay_effect=req.overlay_effect.value,
            parallax_enabled=req.depth_parallax,
            diffusion_cost=0.0,
            render_time_ms=elapsed_ms,
            provenance_json=provenance,
        )
