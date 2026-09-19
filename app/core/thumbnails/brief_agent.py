"""Thumbnail Brief Agent — Emotional Hook Selection and Spoiler-Aware Planning."""
import json
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ThumbnailBrief(BaseModel):
    episode_id: str
    series_title: str
    episode_title: str
    episode_number: int
    hook_summary: str
    spoiler_score: float = Field(..., ge=0.0, le=1.0)
    lead_character_id: str
    wardrobe_id: str
    location_id: Optional[str] = None
    layout_preset: str = "hero_dramatic_close_up"
    artwork_prompts: List[str] = Field(default_factory=list)


class ThumbnailBriefAgent:
    """Produces structured thumbnail briefs balancing emotional hook intensity against spoiler avoidance."""

    SPOILER_KEYWORDS = [
        "dies", "killed", "murderer is", "secret identity revealed", "betrayal",
        "was the killer all along", "poisoned by", "shoots", "arrested for",
    ]

    LAYOUT_PRESETS = [
        "hero_dramatic_close_up",
        "two_character_tension",
        "cliffhanger_reveal_wide",
        "noir_shadow_portrait",
    ]

    @classmethod
    def calculate_spoiler_score(cls, text: Optional[str]) -> float:
        """Scores text on potential narrative spoiler severity (0.0 = safe hook, 1.0 = heavy spoiler)."""
        if not text:
            return 0.05
        score = 0.05
        lower_text = str(text).lower()
        for kw in cls.SPOILER_KEYWORDS:
            if re.search(r"\b" + re.escape(kw) + r"\b", lower_text):
                score += 0.35
        # Clamp between 0.05 and 0.95
        return round(min(0.95, score), 2)

    @classmethod
    def generate_brief(
        cls,
        episode_data: Dict[str, Any],
        continuity_state: Optional[Dict[str, Any]] = None,
    ) -> ThumbnailBrief:
        """Synthesizes an episode emotional hook and produces 4 distinct artwork candidate briefs."""
        ep_id = episode_data.get("episode_id", "ep_01")
        ep_num = int(episode_data.get("episode_number", 1))
        series_title = episode_data.get("series_title", "Preeti Studio Series")
        ep_title = episode_data.get("episode_title", f"Episode {ep_num}")
        synopsis = episode_data.get("synopsis") or ""
        cliffhanger = episode_data.get("cliffhanger_summary") or ""

        # Lead character & wardrobe from continuity state or episode
        lead_char = "CHAR_MAYA_V001"
        wardrobe = "WARDROBE_MAYA_DEFAULT"
        location = "LOC_LOBBY"

        if continuity_state:
            active_chars = continuity_state.get("characters", {})
            if active_chars:
                first_char_id = list(active_chars.keys())[0]
                lead_char = first_char_id
                char_state = active_chars[first_char_id]
                wardrobe = char_state.get("wardrobe_id", wardrobe)
            location = continuity_state.get("location_id", location)

        # Formulate non-spoiler emotional hook
        hook_candidate = cliffhanger if cliffhanger else synopsis
        spoiler_val = cls.calculate_spoiler_score(hook_candidate)
        if spoiler_val >= 0.35:
            # Rephrase into an intriguing question / tension hook
            hook_summary = f"A shocking discovery awaits in {ep_title}."
            spoiler_val = 0.15
        else:
            hook_summary = hook_candidate[:120] if hook_candidate else f"The stakes escalate in {ep_title}."

        layout = cls.LAYOUT_PRESETS[(ep_num - 1) % len(cls.LAYOUT_PRESETS)]

        # Generate 4 distinct artwork prompts
        prompts = [
            (
                f"Cinematic close-up portrait of {lead_char}, intense dramatic expression, "
                f"wearing {wardrobe}, moody rim lighting, sharp filmic 35mm photograph, 8k vertical framing."
            ),
            (
                f"Three-quarter angle portrait of {lead_char} looking toward camera with deep suspense, "
                f"wearing {wardrobe}, cinematic atmospheric lighting, high contrast, cinematic depth of field."
            ),
            (
                f"Dramatic profile angle of {lead_char} in {location}, tense emotion, "
                f"wearing {wardrobe}, warm golden edge lighting, subtle bokeh, premium series keyframe."
            ),
            (
                f"High-impact heroic framing of {lead_char}, resolute gaze, "
                f"wearing {wardrobe}, cinematic anamorphic lens flare, sharp textured vertical poster artwork."
            ),
        ]

        return ThumbnailBrief(
            episode_id=ep_id,
            series_title=series_title,
            episode_title=ep_title,
            episode_number=ep_num,
            hook_summary=hook_summary,
            spoiler_score=spoiler_val,
            lead_character_id=lead_char,
            wardrobe_id=wardrobe,
            location_id=location,
            layout_preset=layout,
            artwork_prompts=prompts,
        )
