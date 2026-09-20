"""Creator Mode API Router — Autonomous Script-to-Screen Execution."""
from typing import Any, Dict, List, Literal
import uuid
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.asset_factory import AssetFactory
from app.core.creator_mode import (
    CreatorModeEngine,
    CreatorModeError,
    CreatorPackage,
    CreatorScriptInput,
    CreatorStoryBeat,
)
from app.core.models import AssetKind
from app.core.run_progress import finish_run, snapshot
from app.core.scene_artist import generate_flux_ai_image

router = APIRouter(prefix="/creator", tags=["creator-mode"])

class ImageGenRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = "9:16"
    seed: int = Field(default=42, ge=0, le=2147483647)
    save_to: str = "shared_assets/uploads"  # where to save


@router.get("/progress/{run_id}")
def creator_progress(run_id: str):
    """Return real render stages, console events, and local resource telemetry."""
    return snapshot(run_id)


@router.post("/parse", response_model=List[CreatorStoryBeat])
def parse_script_beats(req: CreatorScriptInput) -> List[CreatorStoryBeat]:
    """Parses raw text script into normalized dramatic story beats and automated engine routes."""
    try:
        return CreatorModeEngine.normalize_story_beats(req.raw_script_text, req.target_duration_s)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Script parsing error: {str(exc)}")


@router.post("/execute", response_model=CreatorPackage)
def execute_creator_mode(
    req: CreatorScriptInput,
    mock: bool = Query(default=False, description="Run in mock mode for testing"),
) -> CreatorPackage:
    """Executes the complete autonomous Creator Mode pipeline without requiring manual node graph interaction."""
    try:
        return CreatorModeEngine.execute_pipeline(req, mock_mode=mock)
    except CreatorModeError as exc:
        if req.progress_id:
            finish_run(req.progress_id, "failed", str(exc))
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        if req.progress_id:
            finish_run(req.progress_id, "failed", str(exc))
        raise HTTPException(status_code=500, detail=f"Creator mode execution error: {str(exc)}")


@router.post("/generate-image")
def generate_image(req: ImageGenRequest):
    """Generates an image via FLUX AI and saves it locally."""
    if req.aspect_ratio == "16:9":
        width, height = 1344, 768
    elif req.aspect_ratio == "1:1":
        width, height = 1024, 1024
    else:  # 9:16
        width, height = 768, 1344
        
    STUDIO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
    save_dir = STUDIO_ROOT / req.save_to
    save_dir.mkdir(parents=True, exist_ok=True)
    
    unique_id = str(uuid.uuid4())
    output_path = save_dir / f"{unique_id}.png"
    
    success = generate_flux_ai_image(
        prompt_text=req.prompt,
        output_path=str(output_path),
        width=width,
        height=height,
        steps=4,
        timeout_s=1800,
        seed=req.seed,
    )
    
    if not success or not output_path.exists():
        raise HTTPException(status_code=500, detail="Image generation failed")

    try:
        AssetFactory().create_asset(
            project_id="LIBRARY",
            asset_id=f"GEN_{unique_id}",
            kind=AssetKind.KEYFRAME.value,
            name=req.prompt[:80],
            file_path=str(output_path),
        )
    except Exception:
        pass

    return {
        "path": str(output_path).replace("\\", "/"),
        "stream_url": "/api/v1/media/stream?" + urlencode({"path": str(output_path)}),
        "seed": req.seed,
        "prompt": req.prompt
    }
