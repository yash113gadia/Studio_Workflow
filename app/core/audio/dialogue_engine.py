"""Dialogue Timing Pipeline & Scene Timeline Assembly — Chatterbox Multilingual."""
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.audio.voice_registry import VoiceProfile, VoiceRegistry


class DialogueLine(BaseModel):
    character_id: str
    text: str
    emotion: str = "neutral"
    pace_override: Optional[float] = None
    pause_after_s: float = 0.4
    shot_id: Optional[str] = None


class AssembledLineTiming(BaseModel):
    line_index: int
    character_id: str
    voice_id: str
    text: str
    start_time_s: float
    end_time_s: float
    duration_s: float
    pause_after_s: float
    shot_id: Optional[str] = None
    audio_file_path: str


class SceneDialogueAssembly(BaseModel):
    scene_id: str
    project_id: str
    total_duration_s: float
    line_count: int
    lines: List[AssembledLineTiming]
    master_dialogue_audio_path: str


class DialogueEngineError(Exception):
    """Exception raised for dialogue timing and assembly operations."""
    pass


class DialogueEngine:
    """Estimates timing, applies pause markup, and sequences multi-character dialogue."""

    AVERAGE_WORDS_PER_SECOND = 2.4  # ~144 words per minute conversational pace

    @classmethod
    def estimate_text_duration(cls, text: str, pace: float = 1.0) -> float:
        """Estimates speech duration from text and punctuation pause markup."""
        clean_text = text.strip()
        if not clean_text:
            return 0.0

        # Word count contribution
        words = re.findall(r"\b\w+\b", clean_text)
        raw_seconds = len(words) / (cls.AVERAGE_WORDS_PER_SECOND * pace)

        # Punctuation pause contribution
        pause_seconds = 0.0
        pause_seconds += len(re.findall(r"\.\.\.", clean_text)) * 0.6  # Ellipsis
        pause_seconds += len(re.findall(r"[,\;]", clean_text)) * 0.25   # Commas/semicolons
        pause_seconds += len(re.findall(r"[.!?](?!\.)", clean_text)) * 0.45 # Sentences

        # Base minimum duration for short utterances
        return round(max(0.8, raw_seconds + pause_seconds), 2)

    @classmethod
    def assemble_scene_dialogue(
        cls,
        project_id: str,
        scene_id: str,
        dialogue_lines: List[DialogueLine],
        output_dir: Optional[str] = None,
        mock_mode: bool = True,
    ) -> SceneDialogueAssembly:
        """
        Sequences multi-character dialogue lines without overlapping collisions,
        resolving canonical voice profiles, and outputting an aligned scene timeline.
        """
        if not dialogue_lines:
            raise DialogueEngineError("Cannot assemble empty dialogue track.")

        out_path = Path(output_dir or os.path.join(os.getcwd(), "projects", project_id, "renders", "audio")).resolve()
        os.makedirs(out_path, exist_ok=True)

        current_time = 0.0
        assembled_lines: List[AssembledLineTiming] = []

        for idx, line in enumerate(dialogue_lines):
            # Resolve voice for character
            voice = VoiceRegistry.get_character_voice(project_id, line.character_id)
            voice_id = voice.id if voice else f"VOICE_DEFAULT_{line.character_id}"
            pace = line.pace_override or (voice.pace if voice else 1.0)

            line_duration = cls.estimate_text_duration(line.text, pace=pace)
            start_s = round(current_time, 2)
            end_s = round(start_s + line_duration, 2)

            line_filename = f"dialogue_{scene_id}_line_{idx:03d}_{line.character_id}.wav"
            line_file = out_path / line_filename

            # Create line audio WAV
            with open(line_file, "wb") as f:
                f.write(b"RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x08\x00\x00")
                f.write(b"LINE_WAV:" + line.text.encode("utf-8")[:32])

            assembled_lines.append(
                AssembledLineTiming(
                    line_index=idx,
                    character_id=line.character_id,
                    voice_id=voice_id,
                    text=line.text,
                    start_time_s=start_s,
                    end_time_s=end_s,
                    duration_s=line_duration,
                    pause_after_s=line.pause_after_s,
                    shot_id=line.shot_id,
                    audio_file_path=str(line_file),
                )
            )

            # Advance timeline by line duration + conversational pause
            current_time = end_s + line.pause_after_s

        total_duration = round(current_time, 2)
        master_file = out_path / f"master_dialogue_{scene_id}.wav"
        with open(master_file, "wb") as f:
            f.write(b"RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x08\x00\x00")
            f.write(b"MASTER_SCENE_DIALOGUE_STREAM" * 40)

        return SceneDialogueAssembly(
            scene_id=scene_id,
            project_id=project_id,
            total_duration_s=total_duration,
            line_count=len(assembled_lines),
            lines=assembled_lines,
            master_dialogue_audio_path=str(master_file),
        )
