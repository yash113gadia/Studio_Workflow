"""Audio, Voice, Dialogue Timing, Lip-Sync, and Music API Router."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.audio.voice_registry import VoiceProfile, VoiceRegistry, VoiceRegistryError
from app.core.audio.dialogue_engine import (
    DialogueEngine,
    DialogueEngineError,
    DialogueLine,
    SceneDialogueAssembly,
)
from app.core.audio.lipsync_engine import (
    LipSyncEngine,
    LipSyncEngineError,
    LipSyncRequest,
    LipSyncResponse,
)
from app.core.audio.music_engine import (
    MusicBedRequest,
    MusicBedResponse,
    MusicEngine,
    MusicEngineError,
)
from app.core.audio.foley_engine import (
    FoleyEngine,
    FoleyEngineError,
    FoleyRequest,
    FoleyResponse,
)

router = APIRouter(prefix="/audio", tags=["audio"])


class AssembleDialogueRequest(BaseModel):
    project_id: str
    scene_id: str
    lines: List[DialogueLine]


@router.post("/voices", response_model=VoiceProfile)
def register_voice(profile: VoiceProfile) -> VoiceProfile:
    """Registers an authorized canonical voice profile into SQLite."""
    try:
        return VoiceRegistry.register_voice(profile)
    except VoiceRegistryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Voice registration error: {str(exc)}")


@router.get("/voices", response_model=List[VoiceProfile])
def list_voices(project_id: Optional[str] = Query(default=None)) -> List[VoiceProfile]:
    """Lists registered canonical voice profiles."""
    return VoiceRegistry.list_voices(project_id=project_id)


@router.post("/dialogue/assemble", response_model=SceneDialogueAssembly)
def assemble_dialogue(req: AssembleDialogueRequest) -> SceneDialogueAssembly:
    """Estimates speech durations, applies pause markup, and sequences multi-character dialogue."""
    try:
        return DialogueEngine.assemble_scene_dialogue(
            project_id=req.project_id,
            scene_id=req.scene_id,
            dialogue_lines=req.lines,
        )
    except DialogueEngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Dialogue assembly error: {str(exc)}")


@router.post("/lipsync", response_model=LipSyncResponse)
def execute_lipsync(
    req: LipSyncRequest,
    mock: bool = Query(default=True, description="Run in mock mode for testing"),
) -> LipSyncResponse:
    """Executes MuseTalk 1.5 lip sync with facial deformation fallback."""
    try:
        return LipSyncEngine.execute_lipsync(req, mock_mode=mock)
    except LipSyncEngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lip-sync error: {str(exc)}")


@router.post("/music/generate", response_model=MusicBedResponse)
def generate_music(
    req: MusicBedRequest,
    mock: bool = Query(default=True, description="Run in mock mode for testing"),
) -> MusicBedResponse:
    """Generates an ACE-Step 1.5 background music bed snapped to scene duration."""
    try:
        return MusicEngine.generate_music_bed(req, mock_mode=mock)
    except MusicEngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Music generation error: {str(exc)}")


@router.post("/foley", response_model=FoleyResponse)
def generate_foley(
    req: FoleyRequest,
    mock: bool = Query(default=True, description="Run in mock mode for testing"),
) -> FoleyResponse:
    """Generates synchronized Foley sound effects or executes library fallback."""
    try:
        return FoleyEngine.generate_foley(req, mock_mode=mock)
    except FoleyEngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Foley generation error: {str(exc)}")


@router.get("/foley/library")
def get_foley_library() -> Dict[str, Any]:
    """Retrieves the catalog of available sound design and Foley cues."""
    return FoleyEngine.load_manifest()
