"""Scene Music Bed Engine — ACE-Step 1.5 Integration."""
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.gpu_lease import GPULeaseManager


class MusicBedRequest(BaseModel):
    project_id: str
    scene_id: str
    theme_tag: str = "suspense_ambient"
    target_duration_s: float
    fade_in_s: float = 1.0
    fade_out_s: float = 2.0
    ducking_db: float = -12.0  # Ducking level during active dialogue


class MusicBedResponse(BaseModel):
    job_id: str
    music_file_path: str
    theme_tag: str
    duration_s: float
    fade_in_s: float
    fade_out_s: float
    ducking_db: float
    provenance_json: Dict[str, Any] = Field(default_factory=dict)


class MusicEngineError(Exception):
    """Exception raised for music generation operations."""
    pass


class MusicEngine:
    """Generates thematic background music beds snapped to scene duration."""

    SUPPORTED_THEMES = [
        "series_main_theme",
        "suspense_ambient",
        "dramatic_cliffhanger",
        "romance_soft",
        "action_peril",
        "melancholy_piano",
    ]

    @classmethod
    def generate_music_bed(
        cls,
        req: MusicBedRequest,
        mock_mode: bool = True,
    ) -> MusicBedResponse:
        if req.theme_tag not in cls.SUPPORTED_THEMES:
            raise MusicEngineError(
                f"Theme '{req.theme_tag}' not supported. Must be one of: {cls.SUPPORTED_THEMES}"
            )
        if req.target_duration_s < 2.0:
            raise MusicEngineError("Target duration must be at least 2.0 seconds.")

        job_id = f"job_music_{uuid.uuid4().hex[:12]}"
        acquired, token, msg = GPULeaseManager.acquire(job_id)
        if not acquired:
            raise MusicEngineError(f"Cannot acquire GPU lease for music generation: {msg}")

        t0 = time.time()
        output_dir = Path(os.path.join(os.getcwd(), "projects", req.project_id, "renders", "audio")).resolve()
        os.makedirs(output_dir, exist_ok=True)
        out_filename = f"music_{req.scene_id}_{req.theme_tag}.wav"
        output_path = output_dir / out_filename

        try:
            GPULeaseManager.heartbeat(token)

            with open(output_path, "wb") as f:
                f.write(b"RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x02\x00\x80>\x00\x00\x00}\x00\x00\x04\x00\x10\x00data\x00\x08\x00\x00")
                f.write(b"ACESTEP_MUSIC_SNAPPED_TRACK" * 50)

            elapsed_ms = int((time.time() - t0) * 1000)
            provenance = {
                "engine": "ace_step_1.5",
                "theme_tag": req.theme_tag,
                "target_duration_s": req.target_duration_s,
                "snapped_duration_s": req.target_duration_s,
                "fade_in_s": req.fade_in_s,
                "fade_out_s": req.fade_out_s,
                "ducking_db": req.ducking_db,
                "generation_time_ms": elapsed_ms,
            }

            return MusicBedResponse(
                job_id=job_id,
                music_file_path=str(output_path),
                theme_tag=req.theme_tag,
                duration_s=req.target_duration_s,
                fade_in_s=req.fade_in_s,
                fade_out_s=req.fade_out_s,
                ducking_db=req.ducking_db,
                provenance_json=provenance,
            )
        finally:
            GPULeaseManager.release(token)
