from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class JobStatus(str, Enum):
    PENDING = "PENDING"
    BLOCKED = "BLOCKED"
    RUNNING = "RUNNING"
    WAITING_REVIEW = "WAITING_REVIEW"
    SUCCEEDED = "SUCCEEDED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_FINAL = "FAILED_FINAL"
    CANCELLED = "CANCELLED"


class JobKind(str, Enum):
    DUMMY = "dummy"
    NOVEL_PARSE = "novel_parse"
    CANONICAL_CASTING = "canonical_casting"
    CANON_EXTRACT = "canon_extract"
    SEASON_MAP = "season_map"
    KEYFRAME_GEN = "keyframe_gen"
    EDIT_REPAIR = "edit_repair"
    RENDER_SHOT = "render_shot"
    AUDIO_GEN = "audio_gen"
    LIP_SYNC = "lip_sync"
    THUMBNAIL = "thumbnail"
    PACKAGE = "package"


class AssetKind(str, Enum):
    CASTING_CANDIDATE = "casting_candidate"
    CANONICAL_REF = "canonical_ref"
    CANONICAL_ANGLE = "canonical_angle"
    OUTFIT = "outfit"
    LOCATION = "location"
    KEYFRAME = "keyframe"
    EDITED_ASSET = "edited_asset"
    VIDEO_SHOT = "video_shot"
    THUMBNAIL = "thumbnail"


class SpecialistEditAction(str, Enum):
    PRESERVE_IDENTITY_CHANGE_OUTFIT = "preserve_identity_change_outfit"
    REMOVE_UNWANTED_OBJECT = "remove_unwanted_object"
    REPAIR_BACKGROUND = "repair_background"
    DERIVE_ANGLE = "derive_angle"
    CORRECT_PROP = "correct_prop"
    MATERIAL_SWAP = "material_swap"


class SpecialistEditRequest(BaseModel):
    project_id: str
    source_asset_id: str
    action: SpecialistEditAction
    instruction: Optional[str] = None
    seed: Optional[int] = 1000


class SpecialistEditResponse(BaseModel):
    edit_job_id: str
    action: str
    source_asset_id: str
    output_asset_id: str
    status: str
    prompt: str
    seed: int
    provenance_json: Dict[str, Any] = Field(default_factory=dict)


class AssetRecord(BaseModel):
    id: str
    project_id: str
    tier: int = 0
    kind: str
    version: str
    name: str
    file_path: str
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    provenance_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: str



class JobCreate(BaseModel):
    project_id: str
    kind: JobKind = JobKind.DUMMY
    episode_id: Optional[str] = None
    shot_id: Optional[str] = None
    priority: int = 50
    backend: Optional[str] = None
    payload_json: Dict[str, Any] = Field(default_factory=dict)
    max_attempts: int = 3


class JobRecord(BaseModel):
    id: str
    project_id: str
    episode_id: Optional[str] = None
    shot_id: Optional[str] = None
    kind: str
    priority: int
    status: JobStatus
    payload_json: Dict[str, Any] = Field(default_factory=dict)
    attempt: int = 0
    max_attempts: int = 3
    backend: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    heartbeat_at: Optional[str] = None
    error_class: Optional[str] = None
    error_message: Optional[str] = None
    output_asset_ids: List[str] = Field(default_factory=list)


class ProjectKind(str, Enum):
    SERIES = "series"
    CREATOR = "creator"


class ProjectCreate(BaseModel):
    name: str
    kind: ProjectKind = ProjectKind.SERIES
    description: Optional[str] = ""
    style_id: Optional[str] = "STYLE_SERIES_A_V001"
    autonomy_mode: Optional[str] = "review"


class ProjectRecord(BaseModel):
    id: str
    name: str
    kind: ProjectKind
    description: str
    style_id: str
    autonomy_mode: str
    created_at: str
    updated_at: str


class GPULeaseRecord(BaseModel):
    resource: str = "GPU0_HEAVY"
    owner_job_id: Optional[str] = None
    token: Optional[str] = None
    acquired_at: Optional[str] = None
    heartbeat_at: Optional[str] = None
    is_locked: bool = False


class GPULeaseAcquireRequest(BaseModel):
    job_id: str
    requested_seconds: int = 30


class GPULeaseHeartbeatRequest(BaseModel):
    token: str


class GPULeaseReleaseRequest(BaseModel):
    token: str


class SystemHealthResponse(BaseModel):
    status: str = "ok"
    studio_name: str
    version: str
    database_connected: bool
    queue_pending_count: int
    queue_running_count: int
    gpu_lease_status: str
    gpu_lease_owner: Optional[str] = None
    free_disk_gb: float


class H3ShotRequest(BaseModel):
    project_id: str
    keyframe_asset_id: str
    prompt: str
    duration_s: float = Field(default=5.0, ge=3.0, le=8.0)
    aspect: str = "9:16"
    width: int = 480
    height: int = 864
    candidates: int = Field(default=1, ge=1, le=3)
    seed: int = 42
    denoising_priority: str = "lower_vram"
    text_encoder_variant: str = "gguf_q2_k"
    video_vae_variant: str = "fp8mix"
    reference_mode: bool = False
    shot_id: Optional[str] = None
    episode_id: Optional[str] = None


class H3ShotResponse(BaseModel):
    job_id: str
    project_id: str
    status: str
    output_video_asset_id: Optional[str] = None
    output_path: Optional[str] = None
    duration_s: float
    resolution: str
    timings_ms: Dict[str, Any] = Field(default_factory=dict)
    vram_peak_mb: Optional[float] = None
    provenance_json: Dict[str, Any] = Field(default_factory=dict)
