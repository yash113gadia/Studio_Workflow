import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app.core.database import get_db_connection
from app.core.visual_qa.dino_extractor import DINOExtractor
from app.core.visual_qa.canon_registry import CanonVisualRegistry
from app.core.visual_qa.reranker import CandidateReranker
from app.core.visual_qa.drift_tracker import LongitudinalDriftTracker
from app.core.semantic_qa.auditor import SemanticQAAuditor
from app.core.semantic_qa.schema import SemanticAuditRequest, CompositeQADecision, SemanticQAResponse

router = APIRouter(prefix="/qa", tags=["Visual QA & Semantic QA"])

extractor = DINOExtractor()
registry = CanonVisualRegistry(extractor=extractor)
reranker = CandidateReranker(extractor=extractor)
drift_tracker = LongitudinalDriftTracker()
semantic_auditor = SemanticQAAuditor()


class ExtractEmbeddingRequest(BaseModel):
    image_path: str
    crop: Optional[List[float]] = None
    device: str = "cpu"

class RegisterCanonicalRequest(BaseModel):
    project_id: str
    entity_type: str  # 'character', 'wardrobe', 'location'
    entity_id: str
    image_path: str
    sub_slot: str = "CANON_DEFAULT"
    asset_id: Optional[str] = None
    crop: Optional[List[float]] = None

class RerankCandidatesRequest(BaseModel):
    project_id: str
    candidate_paths: List[str]
    shot_id: Optional[str] = None
    ref_char_path: Optional[str] = None
    ref_loc_path: Optional[str] = None
    character_id: Optional[str] = None
    location_id: Optional[str] = None

class RecordDriftRequest(BaseModel):
    project_id: str
    character_id: str
    similarity_to_canonical: float
    shot_id: Optional[str] = None
    scene_id: Optional[str] = None
    episode_id: Optional[str] = None
    candidate_id: Optional[str] = None

@router.post("/extract-embedding")
def extract_embedding_endpoint(req: ExtractEmbeddingRequest):
    try:
        crop_tuple = tuple(req.crop) if req.crop else None
        emb = extractor.extract(req.image_path, crop=crop_tuple, device=req.device)
        return {"dim": len(emb), "embedding": emb}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/register-canonical")
def register_canonical_endpoint(req: RegisterCanonicalRequest):
    try:
        crop_tuple = tuple(req.crop) if req.crop else None
        res = registry.register_canonical_reference(
            project_id=req.project_id,
            entity_type=req.entity_type,
            entity_id=req.entity_id,
            image_path=req.image_path,
            sub_slot=req.sub_slot,
            asset_id=req.asset_id,
            crop=crop_tuple
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/rerank-candidates")
def rerank_candidates_endpoint(req: RerankCandidatesRequest):
    try:
        res = reranker.evaluate_and_rerank(
            project_id=req.project_id,
            candidate_paths=req.candidate_paths,
            shot_id=req.shot_id,
            ref_char_path=req.ref_char_path,
            ref_loc_path=req.ref_loc_path,
            character_id=req.character_id,
            location_id=req.location_id
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/record-drift")
def record_drift_endpoint(req: RecordDriftRequest):
    try:
        res = drift_tracker.record_shot_identity(
            project_id=req.project_id,
            character_id=req.character_id,
            similarity_to_canonical=req.similarity_to_canonical,
            shot_id=req.shot_id,
            scene_id=req.scene_id,
            episode_id=req.episode_id,
            candidate_id=req.candidate_id
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/drift/{project_id}/{character_id}")
def get_drift_history_endpoint(project_id: str, character_id: str):
    return drift_tracker.get_drift_history(project_id, character_id)

@router.get("/evaluations/{shot_id}")
def get_shot_evaluations_endpoint(shot_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM candidate_evaluations
        WHERE shot_id = ?
        ORDER BY rank ASC
    """, (shot_id,))
    rows = cursor.fetchall()
    conn.close()

    evals = []
    for r in rows:
        d = dict(r)
        d["raw_scores"] = json.loads(d["raw_scores_json"])
        d["normalized_scores"] = json.loads(d["normalized_scores_json"])
        d["rejection_reasons"] = json.loads(d["rejection_reasons_json"])
        evals.append(d)

    return {"shot_id": shot_id, "evaluations": evals}

class CompositeDecisionRequest(BaseModel):
    candidate_id: str
    visual_eval: dict
    semantic_eval: SemanticQAResponse
    min_visual_score: float = 0.60

@router.post("/semantic-audit", response_model=SemanticQAResponse)
def semantic_audit_endpoint(req: SemanticAuditRequest):
    try:
        return semantic_auditor.audit_image(
            image_path=req.image_path,
            expected_character=req.expected_character_name,
            expected_wardrobe=req.expected_wardrobe,
            expected_location=req.expected_location,
            required_props=req.required_props,
            expected_injury_state=req.expected_injury_state
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/composite-decision", response_model=CompositeQADecision)
def composite_decision_endpoint(req: CompositeDecisionRequest):
    try:
        return semantic_auditor.evaluate_composite_decision(
            candidate_id=req.candidate_id,
            visual_eval=req.visual_eval,
            semantic_eval=req.semantic_eval,
            min_visual_score=req.min_visual_score
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
