"""Shot-level storyboard API: plan, edit, generate per shot, assemble."""
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core import storyboard as sb
from app.core.models import JobKind
from app.core.queue import DurableQueue
from app.core.run_progress import snapshot

router = APIRouter(prefix="/storyboards", tags=["Storyboard"])


class StoryboardCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    script_text: str = Field(min_length=1, max_length=20000)
    target_duration_s: float = Field(default=30.0, ge=4, le=120)
    project_id: Optional[str] = None
    settings: Dict[str, Any] = Field(default_factory=dict)


class StoryboardPatch(BaseModel):
    title: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class ShotPatch(BaseModel):
    label: Optional[str] = None
    heading: Optional[str] = None
    action: Optional[str] = None
    speaker: Optional[str] = None
    dialogue: Optional[str] = None
    framing: Optional[str] = None
    duration_s: Optional[float] = None
    engine: Optional[str] = None
    camera_motion: Optional[str] = None
    seed: Optional[int] = None
    keyframe_source: Optional[str] = None
    reference_asset_id: Optional[str] = None
    selected_keyframe_id: Optional[str] = None
    selected_clip_id: Optional[str] = None
    selected_speech_id: Optional[str] = None
    notes: Optional[str] = None


class ShotAdd(BaseModel):
    after_shot_id: Optional[str] = None
    action: str = "New shot"
    heading: str = ""
    speaker: str = ""
    dialogue: str = ""
    framing: str = "medium"
    duration_s: float = 4.0
    engine: str = "auto"
    camera_motion: str = "push_in"
    keyframe_source: str = "flux"


class Reorder(BaseModel):
    ordered_ids: List[str]


class KeyframeRequest(BaseModel):
    count: int = Field(default=2, ge=1, le=4)
    keyframe_source: Optional[Literal["flux", "reference", "inherit"]] = None
    reference_asset_id: Optional[str] = None


class ClipRequest(BaseModel):
    engine: Optional[Literal["auto", "2.5d", "ltx", "h3", "scail"]] = None


class AssembleRequest(BaseModel):
    settings: Dict[str, Any] = Field(default_factory=dict)


class FromAsset(BaseModel):
    asset_id: str


class BatchRequest(BaseModel):
    keyframes: bool = True
    speech: bool = True
    clips: bool = True
    assemble: bool = False
    only_missing: bool = True


def _wrap(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except sb.StoryboardError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("")
def list_boards(project_id: Optional[str] = None):
    return {"storyboards": sb.list_storyboards(project_id)}


@router.post("")
def create_board(req: StoryboardCreate):
    return _wrap(sb.create_storyboard, req.title, req.script_text, req.settings, req.project_id, req.target_duration_s)


@router.get("/engines")
def engines():
    return {"motion": sb.available_engines(), "voice": sb.voice_engines(), "music": sb.music_engines()}


@router.get("/{sb_id}")
def get_board(sb_id: str):
    return _wrap(sb.get_storyboard, sb_id)


@router.patch("/{sb_id}")
def patch_board(sb_id: str, req: StoryboardPatch):
    return _wrap(sb.update_storyboard, sb_id, req.model_dump(exclude_none=True))


@router.delete("/{sb_id}")
def delete_board(sb_id: str):
    _wrap(sb.get_storyboard, sb_id)
    sb.delete_storyboard(sb_id)
    return {"deleted": True}


@router.post("/{sb_id}/shots")
def add_shot(sb_id: str, req: ShotAdd):
    data = req.model_dump()
    after = data.pop("after_shot_id")
    return _wrap(sb.add_shot, sb_id, after, **data)


@router.post("/{sb_id}/reorder")
def reorder(sb_id: str, req: Reorder):
    return _wrap(sb.reorder_shots, sb_id, req.ordered_ids)


@router.patch("/shots/{shot_id}")
def patch_shot(shot_id: str, req: ShotPatch):
    return _wrap(sb.update_shot, shot_id, req.model_dump(exclude_unset=True))


@router.delete("/shots/{shot_id}")
def remove_shot(shot_id: str):
    _wrap(sb.delete_shot, shot_id)
    return {"deleted": True}


@router.post("/shots/{shot_id}/keyframes")
def gen_keyframes(shot_id: str, req: KeyframeRequest):
    shot = _wrap(sb.get_shot, shot_id)
    board = sb.get_storyboard(shot["storyboard_id"])
    job = sb.enqueue(JobKind.KEYFRAME_GEN, board, {"shot_id": shot_id, **req.model_dump(exclude_none=True)}, shot_id=shot_id)
    return job


@router.post("/shots/{shot_id}/clip")
def gen_clip(shot_id: str, req: ClipRequest):
    shot = _wrap(sb.get_shot, shot_id)
    board = sb.get_storyboard(shot["storyboard_id"])
    engine = req.engine if req.engine and req.engine != "auto" else None
    return sb.enqueue(JobKind.RENDER_SHOT, board, {"shot_id": shot_id, "engine": engine}, shot_id=shot_id)


@router.post("/shots/{shot_id}/speech")
def gen_speech(shot_id: str):
    shot = _wrap(sb.get_shot, shot_id)
    board = sb.get_storyboard(shot["storyboard_id"])
    return sb.enqueue(JobKind.AUDIO_GEN, board, {"shot_id": shot_id}, shot_id=shot_id, priority=60)


@router.post("/shots/{shot_id}/candidates/from-asset")
def from_asset(shot_id: str, req: FromAsset):
    return _wrap(sb.candidate_from_asset, shot_id, req.asset_id)


@router.post("/candidates/{cand_id}/select")
def select(cand_id: str):
    return _wrap(sb.select_candidate, cand_id)


@router.post("/{sb_id}/speech")
def gen_all_speech(sb_id: str):
    board = _wrap(sb.get_storyboard, sb_id)
    return sb.enqueue(JobKind.AUDIO_GEN, board, {}, priority=60)


@router.post("/{sb_id}/assemble")
def assemble(sb_id: str, req: AssembleRequest):
    board = _wrap(sb.get_storyboard, sb_id)
    return sb.enqueue(JobKind.PACKAGE, board, {"settings": req.settings}, priority=40)


@router.post("/{sb_id}/batch")
def batch(sb_id: str, req: BatchRequest):
    """Queue the whole pipeline in dependency order: speech -> keyframes -> clips -> assemble."""
    board = _wrap(sb.get_storyboard, sb_id)
    jobs = []
    if req.speech and any(s["dialogue"] and (not req.only_missing or not s["selected_speech_id"]) for s in board["shots"]):
        jobs.append(sb.enqueue(JobKind.AUDIO_GEN, board, {}, priority=90))
    for shot in board["shots"]:
        if req.keyframes and (not req.only_missing or not shot["selected_keyframe_id"]):
            jobs.append(sb.enqueue(JobKind.KEYFRAME_GEN, board, {"shot_id": shot["id"]}, shot_id=shot["id"], priority=80))
    for shot in board["shots"]:
        if req.clips and (not req.only_missing or not shot["selected_clip_id"]):
            jobs.append(sb.enqueue(JobKind.RENDER_SHOT, board, {"shot_id": shot["id"], "engine": None}, shot_id=shot["id"], priority=70))
    if req.assemble:
        jobs.append(sb.enqueue(JobKind.PACKAGE, board, {}, priority=40))
    return {"queued": len(jobs), "jobs": jobs}


@router.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = DurableQueue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": job, "progress": snapshot(job_id)}


@router.post("/jobs/{job_id}/cancel")
def cancel(job_id: str):
    job = DurableQueue.cancel_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
