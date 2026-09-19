from typing import List, Optional
from pydantic import BaseModel, Field

class PropRequirement(BaseModel):
    id: str
    present: bool

class SemanticQAResponse(BaseModel):
    characters_visible: int = Field(ge=0, description="Count of distinct human/character figures visible")
    expected_character_match: str = Field(description="'definite', 'likely', 'unlikely', or 'none'")
    outfit_match: bool = Field(description="Whether the visible wardrobe matches expected scene outfit")
    location_match: bool = Field(description="Whether background environment matches expected location")
    required_props: List[PropRequirement] = Field(default_factory=list, description="Verification of mandatory scene props")
    anatomy_warning: bool = Field(default=False, description="Flag for malformed hands, distorted faces, or abnormal limbs")
    continuity_warnings: List[str] = Field(default_factory=list, description="List of continuity inconsistencies detected")
    confidence: float = Field(ge=0.0, le=1.0, description="VLM assessment confidence score")

class SemanticAuditRequest(BaseModel):
    image_path: str
    expected_character_name: Optional[str] = None
    expected_wardrobe: Optional[str] = None
    expected_location: Optional[str] = None
    required_props: Optional[List[str]] = None
    expected_injury_state: Optional[str] = None

class CompositeQADecision(BaseModel):
    candidate_id: str
    is_approved: bool
    final_status: str # "APPROVED", "REJECTED", "ALTERNATIVE"
    visual_score: float
    semantic_confidence: float
    reasons: List[str]
    vlm_summary: Optional[SemanticQAResponse] = None
