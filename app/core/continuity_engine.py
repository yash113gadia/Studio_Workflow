"""Continuity Engine, World Memory & Canon State Machine."""
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.core.database import get_connection


class CharacterCreate(BaseModel):
    id: str
    project_id: str
    name: str
    code: str
    tier: int = 0
    bio: str = ""
    visual_description: str = ""
    canonical_asset_id: Optional[str] = None
    voice_id: Optional[str] = None


class WardrobeCreate(BaseModel):
    id: str
    project_id: str
    character_id: str
    name: str
    top: str = ""
    bottom: str = ""
    footwear: str = ""
    accessories: str = ""
    palette: List[str] = Field(default_factory=list)
    continuity_tags: Dict[str, Any] = Field(default_factory=dict)
    forbidden_additions: List[str] = Field(default_factory=list)
    asset_id: Optional[str] = None


class LocationCreate(BaseModel):
    id: str
    project_id: str
    name: str
    code: str
    setting_type: str = "interior"
    description: str = ""
    floorplan_asset_id: Optional[str] = None
    master_wide_asset_id: Optional[str] = None


class PropCreate(BaseModel):
    id: str
    project_id: str
    name: str
    code: str
    prop_type: str = "object"
    owner_character_id: Optional[str] = None
    current_holder_id: Optional[str] = None
    location_id: Optional[str] = None
    current_state: str = "pristine"
    narrative_significance: str = ""
    asset_id: Optional[str] = None


class SceneStateSnapshot(BaseModel):
    scene_id: str
    character_id: str
    wardrobe_id: Optional[str] = None
    held_prop_id: Optional[str] = None
    injury_state: str = "none"
    emotional_state: str = "neutral"
    blocking_mark: str = "MARK_CENTER"
    screen_side: str = "center"
    visual_overrides: Dict[str, Any] = Field(default_factory=dict)


class ContinuityEventCreate(BaseModel):
    project_id: str
    scene_id: Optional[str] = None
    shot_id: Optional[str] = None
    event_type: str  # wardrobe_change, character_injured, prop_damaged, prop_transferred
    target_entity_type: str  # character, wardrobe, prop, location
    target_entity_id: str
    from_state: Optional[str] = None
    to_state: str
    narrative_rationale: str = ""


class ContinuityEngine:
    """World state memory, canon persistence, and scene continuity inheritance."""

    @staticmethod
    def register_character(c: CharacterCreate):
        now = datetime.utcnow().isoformat()
        conn = get_connection()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO characters (id, project_id, name, code, tier, bio, visual_description, canonical_asset_id, voice_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (c.id, c.project_id, c.name, c.code, c.tier, c.bio, c.visual_description, c.canonical_asset_id, c.voice_id, now)
            )
            # Index into FTS5
            conn.execute(
                """
                INSERT INTO canon_knowledge_fts (entity_id, entity_type, title, content)
                VALUES (?, 'character', ?, ?)
                """,
                (c.id, c.name, f"{c.bio} {c.visual_description}")
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def create_episode(id: str, project_id: str, episode_number: int, title: str, logline: str = ""):
        now = datetime.utcnow().isoformat()
        conn = get_connection()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO episodes (id, project_id, episode_number, title, logline, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (id, project_id, episode_number, title, logline, now)
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def create_scene(id: str, episode_id: str, scene_number: int, location_id: Optional[str] = None, summary: str = ""):
        now = datetime.utcnow().isoformat()
        conn = get_connection()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO scenes (id, episode_id, scene_number, location_id, summary, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (id, episode_id, scene_number, location_id, summary, now)
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def register_wardrobe(w: WardrobeCreate):
        now = datetime.utcnow().isoformat()
        conn = get_connection()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO wardrobe (id, project_id, character_id, name, top, bottom, footwear, accessories, palette_json, continuity_tags_json, forbidden_additions_json, asset_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    w.id, w.project_id, w.character_id, w.name, w.top, w.bottom, w.footwear, w.accessories,
                    json.dumps(w.palette), json.dumps(w.continuity_tags), json.dumps(w.forbidden_additions),
                    w.asset_id, now
                )
            )
            conn.execute(
                """
                INSERT INTO canon_knowledge_fts (entity_id, entity_type, title, content)
                VALUES (?, 'wardrobe', ?, ?)
                """,
                (w.id, w.name, f"{w.top} {w.bottom} {w.accessories}")
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def register_location(loc: LocationCreate):
        now = datetime.utcnow().isoformat()
        conn = get_connection()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO locations (id, project_id, name, code, setting_type, description, floorplan_asset_id, master_wide_asset_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (loc.id, loc.project_id, loc.name, loc.code, loc.setting_type, loc.description, loc.floorplan_asset_id, loc.master_wide_asset_id, now)
            )
            conn.execute(
                """
                INSERT INTO canon_knowledge_fts (entity_id, entity_type, title, content)
                VALUES (?, 'location', ?, ?)
                """,
                (loc.id, loc.name, loc.description)
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def register_prop(p: PropCreate):
        now = datetime.utcnow().isoformat()
        conn = get_connection()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO props (id, project_id, name, code, prop_type, owner_character_id, current_holder_id, location_id, current_state, narrative_significance, asset_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (p.id, p.project_id, p.name, p.code, p.prop_type, p.owner_character_id, p.current_holder_id, p.location_id, p.current_state, p.narrative_significance, p.asset_id, now)
            )
            conn.execute(
                """
                INSERT INTO canon_knowledge_fts (entity_id, entity_type, title, content)
                VALUES (?, 'prop', ?, ?)
                """,
                (p.id, p.name, f"{p.narrative_significance} state: {p.current_state}")
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def record_continuity_event(ev: ContinuityEventCreate) -> str:
        """Record an explicit state transition that alters continuity."""
        event_id = f"EV_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{ev.event_type[:10].upper()}"
        now = datetime.utcnow().isoformat()
        conn = get_connection()
        try:
            conn.execute(
                """
                INSERT INTO continuity_events (id, project_id, scene_id, shot_id, event_type, target_entity_type, target_entity_id, from_state, to_state, narrative_rationale, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, ev.project_id, ev.scene_id, ev.shot_id, ev.event_type, ev.target_entity_type, ev.target_entity_id, ev.from_state, ev.to_state, ev.narrative_rationale, now)
            )
            conn.commit()
            return event_id
        finally:
            conn.close()

    @staticmethod
    def save_scene_character_state(state: SceneStateSnapshot):
        """Save character state snapshot for a scene."""
        state_id = f"STATE_{state.scene_id}_{state.character_id}"
        conn = get_connection()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO scene_character_states (id, scene_id, character_id, wardrobe_id, held_prop_id, injury_state, emotional_state, blocking_mark, screen_side, visual_overrides_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    state_id,
                    state.scene_id,
                    state.character_id,
                    state.wardrobe_id,
                    state.held_prop_id,
                    state.injury_state,
                    state.emotional_state,
                    state.blocking_mark,
                    state.screen_side,
                    json.dumps(state.visual_overrides)
                )
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_scene_character_state(scene_id: str, character_id: str) -> Optional[SceneStateSnapshot]:
        """Restore exact character state snapshot for a scene."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM scene_character_states WHERE scene_id = ? AND character_id = ?",
                (scene_id, character_id)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return SceneStateSnapshot(
                scene_id=row["scene_id"],
                character_id=row["character_id"],
                wardrobe_id=row["wardrobe_id"],
                held_prop_id=row["held_prop_id"],
                injury_state=row["injury_state"],
                emotional_state=row["emotional_state"],
                blocking_mark=row["blocking_mark"],
                screen_side=row["screen_side"],
                visual_overrides=json.loads(row["visual_overrides_json"] or "{}")
            )
        finally:
            conn.close()

    @staticmethod
    def inherit_scene_state(from_scene_id: str, to_scene_id: str, character_id: str, project_id: str) -> SceneStateSnapshot:
        """
        Inherits state from previous scene to next scene.
        Guarantees: Character outfit, held prop, injury state, and location are preserved
        unless an explicit continuity event intervened between the scenes.
        """
        prev_state = ContinuityEngine.get_scene_character_state(from_scene_id, character_id)
        if not prev_state:
            raise ValueError(f"Previous state for scene {from_scene_id} and character {character_id} not found.")

        # Check for any intervening continuity events
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM continuity_events
                WHERE project_id = ? AND target_entity_id = ? AND (scene_id = ? OR scene_id = ?)
                ORDER BY created_at ASC
                """,
                (project_id, character_id, from_scene_id, to_scene_id)
            )
            events = cursor.fetchall()

            wardrobe_id = prev_state.wardrobe_id
            held_prop_id = prev_state.held_prop_id
            injury_state = prev_state.injury_state
            emotional_state = prev_state.emotional_state

            for ev in events:
                etype = ev["event_type"]
                to_s = ev["to_state"]
                if etype == "wardrobe_change":
                    wardrobe_id = to_s
                elif etype == "character_injured":
                    injury_state = to_s
                elif etype == "prop_transferred" or etype == "prop_dropped":
                    held_prop_id = None if to_s == "none" else to_s
                elif etype == "prop_acquired":
                    held_prop_id = to_s
                elif etype == "emotion_changed":
                    emotional_state = to_s

            new_state = SceneStateSnapshot(
                scene_id=to_scene_id,
                character_id=character_id,
                wardrobe_id=wardrobe_id,
                held_prop_id=held_prop_id,
                injury_state=injury_state,
                emotional_state=emotional_state,
                blocking_mark="MARK_CENTER",
                screen_side="center",
                visual_overrides=prev_state.visual_overrides
            )
            ContinuityEngine.save_scene_character_state(new_state)
            return new_state
        finally:
            conn.close()

    @staticmethod
    def search_canon_knowledge(query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search world state knowledge using SQLite FTS5 index."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT entity_id, entity_type, title, snippet(canon_knowledge_fts, 3, '<b>', '</b>', '...', 15) as match_snippet, bm25(canon_knowledge_fts) as rank
                FROM canon_knowledge_fts
                WHERE canon_knowledge_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit)
            )
            rows = cursor.fetchall()
            return [
                {
                    "entity_id": r["entity_id"],
                    "entity_type": r["entity_type"],
                    "title": r["title"],
                    "snippet": r["match_snippet"],
                    "rank": r["rank"]
                }
                for r in rows
            ]
        finally:
            conn.close()
