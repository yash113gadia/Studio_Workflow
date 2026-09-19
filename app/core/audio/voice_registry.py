"""Voice Canon and Consent Registry — Chatterbox Multilingual Voice Assets."""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.database import get_connection


class VoiceProfile(BaseModel):
    id: str
    project_id: str
    character_id: str
    name: str
    engine: str = "chatterbox_multilingual"
    language: str = "hi"
    accent: str = "delhi_urban"
    pace: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=0.0, ge=-10.0, le=10.0)
    canonical_audio_path: str
    pronunciation_notes_json: Dict[str, str] = Field(default_factory=dict)
    consent_verified: bool = True
    created_at: Optional[str] = None


class VoiceRegistryError(Exception):
    """Exception raised for voice registry errors."""
    pass


class VoiceRegistry:
    """Manages canonical voice profiles, audio sample paths, and actor consent."""

    @classmethod
    def register_voice(cls, voice: VoiceProfile) -> VoiceProfile:
        """Registers an authorized canonical voice profile into SQLite."""
        if not voice.consent_verified:
            raise VoiceRegistryError(
                f"Cannot register voice '{voice.name}': actor consent must be verified per Master Plan Rule 6.9."
            )

        if not os.path.exists(voice.canonical_audio_path):
            raise VoiceRegistryError(
                f"Canonical audio WAV missing on disk: {voice.canonical_audio_path}"
            )

        conn = get_connection()
        try:
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                INSERT OR REPLACE INTO voices (
                    id, project_id, character_id, name, engine, language, accent,
                    pace, pitch, canonical_audio_path, pronunciation_notes_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    voice.id,
                    voice.project_id,
                    voice.character_id,
                    voice.name,
                    voice.engine,
                    voice.language,
                    voice.accent,
                    voice.pace,
                    voice.pitch,
                    voice.canonical_audio_path,
                    json.dumps(voice.pronunciation_notes_json),
                    voice.created_at or now_iso,
                ),
            )
            conn.commit()
            voice.created_at = voice.created_at or now_iso
            return voice
        finally:
            conn.close()

    @classmethod
    def get_voice(cls, voice_id: str) -> Optional[VoiceProfile]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM voices WHERE id = ?", (voice_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return VoiceProfile(
                id=row["id"],
                project_id=row["project_id"],
                character_id=row["character_id"],
                name=row["name"],
                engine=row["engine"],
                language=row["language"],
                accent=row["accent"],
                pace=row["pace"],
                pitch=row["pitch"],
                canonical_audio_path=row["canonical_audio_path"],
                pronunciation_notes_json=json.loads(row["pronunciation_notes_json"] or "{}"),
                consent_verified=True,
                created_at=row["created_at"],
            )
        finally:
            conn.close()

    @classmethod
    def get_character_voice(
        cls, project_id: str, character_id: str, language: str = "hi"
    ) -> Optional[VoiceProfile]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM voices WHERE project_id = ? AND character_id = ? AND language = ?",
                (project_id, character_id, language),
            )
            row = cursor.fetchone()
            if not row:
                # Try any language for character
                cursor.execute(
                    "SELECT * FROM voices WHERE project_id = ? AND character_id = ?",
                    (project_id, character_id),
                )
                row = cursor.fetchone()
            if not row:
                return None
            return VoiceProfile(
                id=row["id"],
                project_id=row["project_id"],
                character_id=row["character_id"],
                name=row["name"],
                engine=row["engine"],
                language=row["language"],
                accent=row["accent"],
                pace=row["pace"],
                pitch=row["pitch"],
                canonical_audio_path=row["canonical_audio_path"],
                pronunciation_notes_json=json.loads(row["pronunciation_notes_json"] or "{}"),
                consent_verified=True,
                created_at=row["created_at"],
            )
        finally:
            conn.close()

    @classmethod
    def list_voices(cls, project_id: Optional[str] = None) -> List[VoiceProfile]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            if project_id:
                cursor.execute("SELECT * FROM voices WHERE project_id = ? ORDER BY created_at DESC", (project_id,))
            else:
                cursor.execute("SELECT * FROM voices ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [
                VoiceProfile(
                    id=row["id"],
                    project_id=row["project_id"],
                    character_id=row["character_id"],
                    name=row["name"],
                    engine=row["engine"],
                    language=row["language"],
                    accent=row["accent"],
                    pace=row["pace"],
                    pitch=row["pitch"],
                    canonical_audio_path=row["canonical_audio_path"],
                    pronunciation_notes_json=json.loads(row["pronunciation_notes_json"] or "{}"),
                    consent_verified=True,
                    created_at=row["created_at"],
                )
                for row in rows
            ]
        finally:
            conn.close()
