"""FastAPI REST router for Continuity, World Memory & Canon State Machine."""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.continuity_engine import (
    ContinuityEngine,
    CharacterCreate,
    WardrobeCreate,
    LocationCreate,
    PropCreate,
    SceneStateSnapshot,
    ContinuityEventCreate,
)

router = APIRouter(prefix="/continuity", tags=["Canon & Continuity Engine"])


class InheritStateRequest(BaseModel):
    project_id: str
    from_scene_id: str
    to_scene_id: str
    character_id: str


@router.post("/characters", status_code=status.HTTP_201_CREATED)
def register_character(c: CharacterCreate):
    ContinuityEngine.register_character(c)
    return {"status": "created", "character_id": c.id}


@router.post("/wardrobe", status_code=status.HTTP_201_CREATED)
def register_wardrobe(w: WardrobeCreate):
    ContinuityEngine.register_wardrobe(w)
    return {"status": "created", "wardrobe_id": w.id}


@router.post("/locations", status_code=status.HTTP_201_CREATED)
def register_location(loc: LocationCreate):
    ContinuityEngine.register_location(loc)
    return {"status": "created", "location_id": loc.id}


@router.post("/props", status_code=status.HTTP_201_CREATED)
def register_prop(p: PropCreate):
    ContinuityEngine.register_prop(p)
    return {"status": "created", "prop_id": p.id}


@router.post("/events", status_code=status.HTTP_201_CREATED)
def record_event(ev: ContinuityEventCreate):
    event_id = ContinuityEngine.record_continuity_event(ev)
    return {"status": "recorded", "event_id": event_id}


@router.post("/scenes/state", status_code=status.HTTP_200_OK)
def save_scene_state(state: SceneStateSnapshot):
    ContinuityEngine.save_scene_character_state(state)
    return {"status": "saved", "scene_id": state.scene_id, "character_id": state.character_id}


@router.get("/scenes/{scene_id}/character/{character_id}", response_model=SceneStateSnapshot)
def get_scene_state(scene_id: str, character_id: str):
    state = ContinuityEngine.get_scene_character_state(scene_id, character_id)
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="State not found for scene and character.")
    return state


@router.post("/scenes/inherit", response_model=SceneStateSnapshot)
def inherit_scene_state(req: InheritStateRequest):
    try:
        return ContinuityEngine.inherit_scene_state(
            from_scene_id=req.from_scene_id,
            to_scene_id=req.to_scene_id,
            character_id=req.character_id,
            project_id=req.project_id
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/search")
def search_canon(q: str, limit: int = 10):
    """FTS5 search across canon knowledge, character bios, and wardrobe details."""
    try:
        return ContinuityEngine.search_canon_knowledge(q, limit)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
