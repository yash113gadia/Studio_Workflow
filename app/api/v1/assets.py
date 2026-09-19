from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.core.models import AssetRecord, AssetKind
from app.core.asset_factory import AssetFactory

router = APIRouter(prefix="/assets", tags=["assets"])


class CastingCreateRequest(BaseModel):
    project_id: str
    character_name: str
    prompt_description: str
    count: int = 3
    seed_base: int = 1000


class CastingApproveRequest(BaseModel):
    project_id: str
    candidate_asset_id: str
    character_code: str
    approval_actor: str = "studio_admin"


class CanonicalAnglesRequest(BaseModel):
    project_id: str
    canonical_id: str
    seed_base: int = 2000


@router.post("/casting/create", response_model=List[Dict[str, Any]])
def create_casting_session(req: CastingCreateRequest):
    factory = AssetFactory()
    try:
        jobs = factory.create_casting_jobs(
            project_id=req.project_id,
            character_name=req.character_name,
            prompt_description=req.prompt_description,
            count=req.count,
            seed_base=req.seed_base
        )
        return jobs
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/casting/approve", response_model=AssetRecord)
def approve_casting_candidate(req: CastingApproveRequest):
    factory = AssetFactory()
    try:
        canonical = factory.approve_character_casting(
            project_id=req.project_id,
            candidate_asset_id=req.candidate_asset_id,
            character_code=req.character_code,
            approval_actor=req.approval_actor
        )
        return canonical
    except ValueError as ve:
        raise HTTPException(status_code=409, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/canonical/angles", response_model=List[Dict[str, Any]])
def create_canonical_angles(req: CanonicalAnglesRequest):
    factory = AssetFactory()
    try:
        jobs = factory.create_canonical_angle_jobs(
            project_id=req.project_id,
            canonical_id=req.canonical_id,
            seed_base=req.seed_base
        )
        return jobs
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{asset_id}", response_model=AssetRecord)
def get_asset(asset_id: str):
    factory = AssetFactory()
    asset = factory.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found")
    return asset


@router.get("/project/{project_id}", response_model=List[AssetRecord])
def list_project_assets(project_id: str, kind: Optional[str] = None):
    factory = AssetFactory()
    return factory.list_assets(project_id, kind=kind)
