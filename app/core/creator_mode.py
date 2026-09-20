"""Creator Mode Engine — Fully Autonomous 30-60s Script-to-Screen Pipeline."""
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field

from app.core.models import AssetKind, ProjectCreate, ProjectKind
from app.core.asset_factory import AssetFactory
from app.core.render_guard import exclusive_render
from app.core.run_progress import emit as progress_emit, finish_run, start_run
from app.core.projects import ProjectManager
from app.core.audio.dialogue_engine import DialogueEngine, DialogueLine
from app.core.audio.music_engine import MusicBedRequest, MusicEngine
from app.core.audio.foley_engine import (
    FoleyBackend,
    FoleyCategory,
    FoleyCue,
    FoleyEngine,
    FoleyRequest,
)
from app.core.post.renderer_25d import (
    Motion25DType,
    OverlayEffectType,
    Render25DRequest,
    Renderer25D,
)
from app.core.post.assembly_engine import (
    AssemblyEngine,
    AssemblyRequest,
    ShotClipInput,
    SubtitleEntry,
)
from app.core.thumbnails.thumbnail_manager import (
    ThumbnailGenerationRequest,
    ThumbnailManager,
)
from app.core.scene_artist import render_cinematic_keyframe, render_shot_video_clip
from app.core.audio.speech_synth import synthesize_speech, synthesize_music_bed
from app.core.frame_interpolation import interpolate_video_2x


class CreatorScriptInput(BaseModel):
    project_id: Optional[str] = None
    title: str = "The Midnight Encounter"
    raw_script_text: str = Field(min_length=1, max_length=20000)
    target_duration_s: float = Field(default=40.0, ge=4, le=120)
    genre: str = "suspense_drama"
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = "9:16"
    render_mode: Literal["auto", "cinematic", "generative"] = "auto"
    progress_id: Optional[str] = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,80}$")
    seed: int = Field(default=42, ge=0, le=2147483647)
    quality_profile: Literal["draft", "balanced", "quality"] = "balanced"
    voice_engine: Literal["windows_sapi"] = "windows_sapi"
    music_engine: Literal["off", "procedural"] = "off"
    foley_engine: Literal["off", "library"] = "off"
    qa_mode: Literal["off", "dino"] = "dino"
    upscale_engine: Literal["lanczos"] = "lanczos"
    frame_interpolation: Literal["off", "film_2x"] = "off"
    burn_subtitles: bool = True
    reference_image_path: Optional[str] = None


def resolve_reference_image(raw_path: Optional[str]) -> Optional[Path]:
    """Validate a user-supplied reference image lives inside Studio-managed media roots."""
    if not raw_path:
        return None
    root = Path(__file__).resolve().parents[2]
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    approved = [(root / name).resolve() for name in ("shared_assets", "projects", "cache")]
    if not any(candidate.is_relative_to(base) for base in approved):
        raise CreatorModeError("Reference image must come from the Studio asset library.")
    if not candidate.is_file() or candidate.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise CreatorModeError(f"Reference image not found or not an image: {raw_path}")
    return candidate


class CreatorStoryBeat(BaseModel):
    beat_number: int
    heading: str
    action: str
    dialogue: List[Dict[str, str]] = Field(default_factory=list)
    characters: List[str] = Field(default_factory=list)
    location: str = ""
    duration_s: float = 8.0
    recommended_route: str = "2.5d"  # '2.5d', 'scail_motion', 'h3_generative'
    shot_framing: str = "medium_close_up"


class CreatorShotSpec(BaseModel):
    shot_id: str
    beat_number: int
    engine: str
    character_id: Optional[str] = None
    wardrobe_id: Optional[str] = None
    location_id: Optional[str] = None
    motion_id: Optional[str] = None
    duration_s: float = 6.0
    dialogue_line: Optional[str] = None
    speaker: Optional[str] = None
    foley_cues: List[str] = Field(default_factory=list)


class CreatorPackage(BaseModel):
    project_id: str
    package_id: str
    title: str
    master_video_path: str
    subtitles_srt_path: str
    thumbnail_variants: Dict[str, str]
    qa_report: Dict[str, Any]
    story_beats: List[CreatorStoryBeat]
    shots_executed: List[CreatorShotSpec]
    audio_summary: Dict[str, Any]
    total_duration_s: float
    runtime_ms: int
    provenance_sidecar_path: str


class CreatorModeError(Exception):
    """Exception raised by Creator Mode autonomous pipeline."""
    pass


class CreatorModeEngine:
    """End-to-End autonomous short video generation pipeline from raw script to final package."""

    @classmethod
    def normalize_story_beats(cls, raw_script: str, target_duration_s: float = 40.0) -> List[CreatorStoryBeat]:
        """Parses raw text script into normalized, sequenced dramatic beats."""
        if not raw_script.strip():
            raise CreatorModeError("Please enter a script containing text.")
        lines = [line.strip() for line in raw_script.strip().split("\n") if line.strip()]
        beats: List[CreatorStoryBeat] = []

        current_heading = "Scene 1: Introduction"
        current_action = ""
        current_dialogue: List[Dict[str, str]] = []
        current_chars: set = set()
        pending_speaker = None

        METADATA_KEYS = {
            "VISUAL", "CAMERA", "SOUND", "ACTION", "LIGHTING", "TEXT", "TEXT ON SCREEN",
            "FORMAT", "TONE", "STYLE", "DURATION", "TIME", "NOTE", "IMPORTANT", "END",
            "TITLE", "MUSIC", "FOLEY", "PROMPT", "SETTING"
        }
        NON_CHARACTER_WORDS = {
            "STEAM", "CUT", "FADE", "BEAT", "NIGHT", "DAY", "EXT", "INT",
            "CONTINUOUS", "FLASHBACK", "POV", "CLOSE", "WIDE", "SCENE", "VOICEOVER", "END"
        }

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check for scene heading (e.g. INT. / EXT. / SCENE)
            if re.match(r"^(INT\.|EXT\.|SCENE\b)", line, re.IGNORECASE):
                if current_action or current_dialogue:
                    beats.append(
                        cls._build_beat(len(beats) + 1, current_heading, current_action, current_dialogue, sorted(current_chars))
                    )
                    current_action = ""
                    current_dialogue = []
                    current_chars = set()
                    pending_speaker = None
                current_heading = line
                i += 1
                continue

            # Check for colon format: "DIYA: The transmission is locked." or "Visual: ..." or "0-3 sec: ..."
            if ":" in line and not line.startswith("http"):
                parts = line.split(":", 1)
                prefix = parts[0].strip().upper()
                content = parts[1].strip().strip('"\'“”')

                # Voiceover timing cue: e.g. "0-3 sec" or "VOICEOVER" or "NARRATOR"
                if re.match(r"^\d+\s*[-–—to]+\s*\d+\s*(sec|s)?$", prefix, re.IGNORECASE) or prefix in ("VOICEOVER", "VO", "NARRATOR", "V.O."):
                    if content:
                        current_dialogue.append({"speaker": "NARRATOR", "text": content})
                        current_chars.add("NARRATOR")
                    i += 1
                    continue

                # Directive / metadata key: append visual/action content to current_action, skip pure metadata
                if prefix in METADATA_KEYS:
                    if prefix in ("ACTION", "VISUAL", "LIGHTING", "PROMPT", "SETTING") and content:
                        current_action += (" " + content if current_action else content)
                    i += 1
                    continue

                # Regular character speaker
                if prefix not in NON_CHARACTER_WORDS and len(prefix) <= 25 and not re.search(r"[\d.,?!;]", prefix):
                    current_dialogue.append({"speaker": prefix, "text": content})
                    current_chars.add(prefix)
                    i += 1
                    continue

            # Check for standard Hollywood screenplay format:
            # Line 1: CHARACTER (all uppercase, 2-25 chars)
            # Line 2 (optional): (parenthetical)
            # Line 3: Spoken dialogue line
            is_char_header = (
                line.isupper()
                and 2 <= len(line) <= 25
                and not any(char in line for char in [".", ",", "!", "?", "-", ":"])
                and line not in NON_CHARACTER_WORDS
                and line not in METADATA_KEYS
            )
            if is_char_header and (i + 1) < len(lines):
                speaker_cand = line
                next_line = lines[i + 1]
                # Check for parenthetical on next line
                if next_line.startswith("(") and next_line.endswith(")") and (i + 2) < len(lines):
                    speech_line = lines[i + 2]
                    current_dialogue.append({"speaker": speaker_cand, "text": speech_line})
                    current_chars.add(speaker_cand)
                    i += 3
                    continue
                elif not next_line.isupper() and not next_line.startswith("SCENE") and not next_line.startswith("EXT") and not next_line.startswith("INT"):
                    current_dialogue.append({"speaker": speaker_cand, "text": next_line})
                    current_chars.add(speaker_cand)
                    i += 2
                    continue

            # Otherwise, treat as action line
            current_action += (" " + line if current_action else line)
            for word in line.split():
                clean_word = re.sub(r"[^\w]", "", word)
                if clean_word.isupper() and 2 < len(clean_word) <= 20 and clean_word not in NON_CHARACTER_WORDS and clean_word not in METADATA_KEYS:
                    current_chars.add(clean_word)
            i += 1

        if current_action or current_dialogue:
            beats.append(
                cls._build_beat(len(beats) + 1, current_heading, current_action, current_dialogue, sorted(current_chars))
            )

        # Filter out empty preamble beat if it only captured metadata before the first scene
        if len(beats) > 1 and not beats[0].dialogue and len(beats[0].action) < 60 and ("RAT ATE" in beats[0].action or "Scene 1: Introduction" in beats[0].heading):
            # Check if beat 2 has Scene 1
            if "Scene 1" in beats[1].heading:
                beats.pop(0)
                for idx, b in enumerate(beats, start=1):
                    b.beat_number = idx

        if not beats:
            # Fallback single beat
            beats.append(
                cls._build_beat(1, "Scene 1: Main Action", raw_script, [], [])
            )

        # Distribute target duration across beats
        per_beat_dur = round(target_duration_s / max(1, len(beats)), 1)
        for b in beats:
            b.duration_s = max(4.0, per_beat_dur)

        return beats

    @classmethod
    def _build_beat(
        cls,
        num: int,
        heading: str,
        action: str,
        dialogue: List[Dict[str, str]],
        chars: List[str],
    ) -> CreatorStoryBeat:
        """Determines engine routing and shot parameters for a story beat."""
        lower_action = action.lower()
        if dialogue:
            # Dialogue shot -> SCAIL controlled motion
            route = "scail_motion"
            framing = "medium_close_up"
        elif any(k in lower_action for k in ["explodes", "runs", "combat", "fight", "chase", "shatters"]):
            # High action -> H3 generative
            route = "h3_generative"
            framing = "wide_dynamic"
        else:
            # Subtle reaction / environment / insert -> 2.5D cheap-shot
            route = "2.5d"
            framing = "dramatic_push_insert"

        return CreatorStoryBeat(
            beat_number=num,
            heading=heading,
            action=action or "Dramatic moment unfolds.",
            dialogue=dialogue,
            characters=chars,
            duration_s=6.0,
            recommended_route=route,
            shot_framing=framing,
        )

    @classmethod
    def plan_shots(cls, beats: List[CreatorStoryBeat]) -> List[Dict[str, Any]]:
        import math
        shots = []
        for beat in beats:
            count = max(len(beat.dialogue), math.ceil(beat.duration_s / 5.0))
            for index in range(count):
                line = beat.dialogue[index] if index < len(beat.dialogue) else {}
                speaker = line.get("speaker", "")
                shots.append({
                    "shot_id": f"shot_beat_{beat.beat_number:02d}_{index + 1:02d}",
                    "beat_number": beat.beat_number, "engine": beat.recommended_route,
                    "duration_s": beat.duration_s / count,
                    "framing": "medium_close_up" if line else ("wide_establishing" if index == 0 else "medium"),
                    "heading": beat.heading, "action": beat.action,
                    "speaker": speaker, "dialogue_line": line.get("text"),
                })
        return shots

    @classmethod
    @exclusive_render
    def execute_pipeline(
        cls,
        input_data: CreatorScriptInput,
        mock_mode: bool = False,
    ) -> CreatorPackage:
        """Executes the full automated Creator Mode pipeline without requiring manual node graph interaction."""
        t0 = time.time()
        package_id = f"pkg_{uuid.uuid4().hex[:12]}"
        run_id = input_data.progress_id or package_id
        start_run(run_id, input_data.title)
        progress_emit(run_id, "project", "Creating the project workspace and output package.", 3)

        # Step 1: Ensure or create project
        if input_data.project_id:
            project_id = input_data.project_id
        else:
            proj = ProjectManager.create_project(
                ProjectCreate(
                    name=input_data.title,
                    kind=ProjectKind.CREATOR,
                    description=f"Creator mode automated package: {input_data.title}",
                )
            )
            project_id = proj.id

        root = Path(__file__).resolve().parents[2]
        out_dir = (root / "cache" / "mock_renders" / package_id) if mock_mode else (root / "projects" / project_id / "renders" / "creator_mode" / package_id)
        os.makedirs(out_dir, exist_ok=True)

        # Step 2: Normalize story beats & extract entities
        story_beats = cls.normalize_story_beats(input_data.raw_script_text, input_data.target_duration_s)

        # Preserve every dialogue line and keep shots short enough for local generation.
        shots_plan = cls.plan_shots(story_beats)
        progress_emit(
            run_id, "planning",
            f"Parsed {len(story_beats)} story beat(s) into {len(shots_plan)} shot(s).",
            7, total_shots=len(shots_plan),
        )
        target_width, target_height = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}[input_data.aspect_ratio]
        reference_image = resolve_reference_image(input_data.reference_image_path)
        warnings = []
        if reference_image:
            warnings.append("Reference image used as the keyframe for every shot; FLUX keyframe generation skipped.")
        if input_data.render_mode == "cinematic":
            warnings.append("Cinematic mode uses camera motion over AI stills; it does not animate actors or lip-sync.")
        elif input_data.render_mode == "auto":
            warnings.append("Auto mode protects dialogue and hand-detail shots with stable cinematic motion and reserves LTX for safer shots.")
        audio_dir = out_dir / "audio"
        audio_dir.mkdir(exist_ok=True)
        voice_indices = {name: index for index, name in enumerate(sorted({s["speaker"] for s in shots_plan if s["dialogue_line"]}))}
        # Measure speech before rendering so dialogue cannot be cut off by the shot.
        for shot_index, s in enumerate(shots_plan, start=1):
            if s["dialogue_line"] and not mock_mode:
                progress_emit(run_id, "speech", f"Synthesizing dialogue for shot {shot_index}/{len(shots_plan)}.", 8)
                import wave
                speech_path = str(audio_dir / (s["shot_id"] + ".wav"))
                if not synthesize_speech(s["dialogue_line"], speech_path, voice_index=voice_indices[s["speaker"]]):
                    raise CreatorModeError(f"Speech synthesis failed for {s['shot_id']}; no tone substituted.")
                with wave.open(speech_path, "rb") as wav:
                    speech_duration = wav.getnframes() / wav.getframerate()
                s["speech_path"] = speech_path
                s["speech_duration"] = speech_duration
                s["duration_s"] = max(s["duration_s"], speech_duration + 0.6)

        shots_specs: List[CreatorShotSpec] = []
        shot_clips: List[ShotClipInput] = []
        subtitles: List[SubtitleEntry] = []
        current_time_s = 0.0

        keyframe_cache = {}
        for shot_index, s in enumerate(shots_plan, start=1):
            shot_id = s["shot_id"]
            speaker = s["speaker"]
            speech_text = s["dialogue_line"]
            framing = s["framing"]
            dur = s["duration_s"]

            risky_human_motion = any(word in s["action"].lower() for word in (
                "hand", "phone", "display", "screen", "grip", "hold", "face", "walk", "run", "fight", "dance"
            ))
            if input_data.render_mode == "generative":
                shot_engine = "ltx_i2v"
            elif input_data.render_mode == "cinematic":
                shot_engine = "2.5d"
            else:
                shot_engine = "2.5d" if s["dialogue_line"] or risky_human_motion else "ltx_i2v"
            spec = CreatorShotSpec(
                shot_id=shot_id,
                beat_number=s["beat_number"],
                engine="mock" if mock_mode else shot_engine,
                character_id=None,
                wardrobe_id=None,
                location_id=None,
                duration_s=dur,
                dialogue_line=speech_text,
                speaker=speaker,
                foley_cues=[],
            )
            shots_specs.append(spec)

            # Synthesize real cinematic shot video file
            kf_file = str(out_dir / f"{shot_id}_keyframe.jpg")
            shot_video_file = str(out_dir / f"{shot_id}.mp4")

            clip_ok = False
            if mock_mode:
                try:
                    from PIL import Image, ImageDraw
                    mock_img = Image.new("RGB", (1080, 1920), color=(15 + s["beat_number"] * 10, 20, 35 + s["beat_number"] * 15))
                    draw = ImageDraw.Draw(mock_img)
                    draw.text((100, 900), f"PREETI STUDIO MOCK\n{input_data.title}\n{shot_id} [{framing}]", fill=(220, 230, 255))
                    mock_img.save(kf_file, "JPEG", quality=90)
                except Exception:
                    pass

                from app.core.post.ffmpeg_utils import run_ffmpeg
                cmd = [
                    "-f", "lavfi",
                    "-i", f"color=c=0x0a0c14:s=1080x1920:d={dur}:r=24",
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p",
                    "-y",
                    str(shot_video_file),
                ]
                run_ffmpeg(cmd, timeout_s=15)
                clip_ok = os.path.exists(shot_video_file)
            else:
                try:
                    progress_emit(
                        run_id, "keyframe",
                        f"Shot {shot_index}/{len(shots_plan)}: "
                        + ("fitting reference image as keyframe." if reference_image else f"preparing FLUX keyframe ({framing})."),
                        10 + int(45 * (shot_index - 1) / max(1, len(shots_plan))),
                        current_shot=shot_index,
                    )
                    # Reuse a scene's established subject instead of recasting on every cut.
                    if reference_image:
                        from PIL import Image, ImageOps
                        ref_img = Image.open(reference_image).convert("RGB")
                        ImageOps.fit(ref_img, (target_width, target_height), method=Image.Resampling.LANCZOS).save(kf_file, "JPEG", quality=95)
                    elif s["beat_number"] in keyframe_cache:
                        import shutil
                        shutil.copy2(keyframe_cache[s["beat_number"]], kf_file)
                    else:
                        render_cinematic_keyframe(
                            title=input_data.title,
                            scene_heading=s["heading"],
                            speaker=speaker,
                            dialogue=speech_text,
                            genre=input_data.genre,
                            beat_number=s["beat_number"],
                            output_image_path=kf_file,
                            action=s["action"],
                            framing=framing,
                            width=target_width, height=target_height,
                            seed=input_data.seed + len(shots_specs),
                            progress_client_id=run_id,
                        )
                        keyframe_cache[s["beat_number"]] = kf_file
                    try:
                        AssetFactory().create_asset(
                            project_id=project_id,
                            asset_id=f"KEYFRAME_{package_id}_{shot_id}",
                            kind=AssetKind.KEYFRAME.value,
                            name=f"{shot_id} keyframe",
                            file_path=kf_file,
                        )
                    except Exception:
                        pass
                    progress_emit(
                        run_id, "motion",
                        f"Shot {shot_index}/{len(shots_plan)}: rendering with {shot_engine} for {dur:.1f}s.",
                        15 + int(50 * (shot_index - 1) / max(1, len(shots_plan))),
                        current_shot=shot_index,
                    )
                    if shot_engine == "ltx_i2v":
                        from app.core.local_video import render_ltx_video
                        # LTX reports 18..62 for a single clip; remap into this shot's slice of the 15..65 motion band.
                        shot_start = 15 + 50 * (shot_index - 1) / max(1, len(shots_plan))
                        shot_span = 50 / max(1, len(shots_plan))
                        clip_ok = render_ltx_video(
                            kf_file, shot_video_file, s["action"], dur,
                            input_data.aspect_ratio, input_data.seed + len(shots_specs),
                            quality_profile=input_data.quality_profile,
                            client_id=run_id,
                            progress_callback=lambda message, pct: progress_emit(
                                run_id, "motion", f"Shot {shot_index}/{len(shots_plan)}: {message}",
                                int(shot_start + shot_span * min(1.0, max(0.0, (pct - 18) / 44))),
                                current_shot=shot_index,
                            ),
                        )
                    else:
                        clip_ok = render_shot_video_clip(
                            image_path=kf_file, output_mp4_path=shot_video_file,
                            duration_s=dur, beat_number=s["beat_number"], framing=framing,
                            width=target_width, height=target_height, genre=input_data.genre,
                        )
                except Exception as exc:
                    raise CreatorModeError(f"Shot {shot_id} failed: {exc}") from exc
                if not clip_ok or not os.path.exists(shot_video_file) or os.path.getsize(shot_video_file) < 1000:
                    raise CreatorModeError(f"Shot {shot_id} produced no valid video; generation stopped.")

            shot_clips.append(
                ShotClipInput(
                    shot_id=shot_id,
                    video_path=shot_video_file,
                    in_trim_s=0.0,
                    out_trim_s=dur,
                )
            )

            # Subtitle entry if speech present
            if speech_text:
                subtitles.append(
                    SubtitleEntry(
                        start_s=round(current_time_s + 0.3, 2),
                        end_s=round(current_time_s + 0.3 + s.get("speech_duration", dur - 0.6), 2),
                        text=speech_text,
                        character_name=speaker.capitalize(),
                    )
                )

            current_time_s += dur
            progress_emit(
                run_id, "shot_complete",
                f"Shot {shot_index}/{len(shots_plan)} completed and validated on disk.",
                15 + int(50 * shot_index / max(1, len(shots_plan))), current_shot=shot_index,
            )

        total_duration = current_time_s

        # Step 4: Audio Track Generation (Real Dialogue, Foley, Ducked Music Bed)
        progress_emit(run_id, "audio", "Assembling dialogue, Foley, and music stems.", 68)
        audio_dir = out_dir / "audio"
        os.makedirs(audio_dir, exist_ok=True)
        dialogue_wav = str(audio_dir / "dialogue_master.wav")
        foley_wav = str(audio_dir / "foley_master.wav")
        music_wav = str(audio_dir / "music_bed.wav")

        speech_ok = False
        if not mock_mode:
            from app.core.audio.speech_synth import assemble_speech_timeline
            speech_ok = assemble_speech_timeline(shots_plan, dialogue_wav, total_duration)
        foley_ok = False
        foley_result = None
        if input_data.foley_engine == "library" and not mock_mode:
            cues = []
            cursor_s = 0.0
            for shot in shots_plan:
                action = shot["action"].lower()
                if any(word in action for word in ("walk", "step", "run", "dash", "chase")):
                    cues.append(FoleyCue(
                        action_type=FoleyCategory.FOOTSTEPS,
                        cue_id="SFX_FOOTSTEPS_CONCRETE_V001",
                        start_time_s=cursor_s + 0.2,
                        duration_s=min(2.5, shot["duration_s"]),
                        gain_db=-5.0,
                        description="Action-matched footsteps",
                    ))
                if "door" in action:
                    cues.append(FoleyCue(
                        action_type=FoleyCategory.DOORS,
                        cue_id="SFX_DOOR_OPEN_CREAK_V001",
                        start_time_s=cursor_s + 0.2,
                        duration_s=1.5,
                        gain_db=-4.0,
                        description="Action-matched door movement",
                    ))
                if any(word in action for word in ("hit", "punch", "fall", "slam", "impact", "fight")):
                    cues.append(FoleyCue(
                        action_type=FoleyCategory.IMPACT,
                        cue_id="SFX_IMPACT_TABLE_THUMP_V001",
                        start_time_s=cursor_s + min(0.7, shot["duration_s"] / 2),
                        duration_s=1.0,
                        gain_db=-3.0,
                        description="Action-matched impact",
                    ))
                cursor_s += shot["duration_s"]
            cues.insert(0, FoleyCue(
                action_type=FoleyCategory.AMBIENCE,
                cue_id="SFX_AMBIENCE_ROOM_TONE_V001",
                start_time_s=0.0,
                duration_s=total_duration,
                gain_db=-15.0,
                description="Low-level ambience bed",
            ))
            foley_result = FoleyEngine.generate_foley(FoleyRequest(
                project_id=project_id,
                shot_id=package_id,
                duration_s=total_duration,
                backend=FoleyBackend.LIBRARY_FALLBACK,
                cues=cues,
                output_dir=str(audio_dir),
            ), mock_mode=False)
            foley_wav = foley_result.audio_path or foley_wav
            foley_ok = bool(foley_result.audio_path and Path(foley_result.audio_path).exists())

        music_ok = False
        if input_data.music_engine == "procedural" and not mock_mode:
            music_ok = synthesize_music_bed(input_data.genre, total_duration, music_wav)
            warnings.append("Background music is a procedural ambient bed, not neural music generation.")

        # Step 5: Post Assembly (Exact trims, concats, loudness normalization, 1080x1920 encode)
        progress_emit(run_id, "assembly", f"Encoding the {target_width}x{target_height} master and subtitles.", 78)
        assembly_req = AssemblyRequest(
            project_id=project_id,
            sequence_id=package_id,
            shots=shot_clips,
            dialogue_audio_path=dialogue_wav if speech_ok else None,
            foley_audio_path=foley_wav if foley_ok else None,
            music_audio_path=music_wav if music_ok else None,
            music_ducking_db=-12.0,
            subtitles=subtitles,
            burn_subtitles=input_data.burn_subtitles,
            target_width=target_width,
            target_height=target_height,
            output_dir=str(out_dir),
        )
        assembly_res = AssemblyEngine.assemble(assembly_req, mock_mode=mock_mode)
        if input_data.frame_interpolation == "film_2x" and not mock_mode:
            progress_emit(run_id, "frame_interpolation", "Running verified FILM 2x interpolation on the assembled master.", 84)
            interpolated_path = str(Path(assembly_res.master_video_path).with_name(
                Path(assembly_res.master_video_path).stem + "_film2x.mp4"
            ))
            interpolate_video_2x(assembly_res.master_video_path, interpolated_path, client_id=run_id)
            assembly_res.master_video_path = interpolated_path
            assembly_res.provenance_json["frame_interpolation"] = "FILM 2x"
            warnings.append("FILM 2x interpolation was applied after assembly; inspect fast movement for ghosting.")

        # Step 6: Thumbnail Generation (Brief + 4 candidates + QA + typography)
        progress_emit(run_id, "thumbnails", "Creating thumbnail variants from the rendered material.", 86)
        # Select best character keyframe (prefer hero close-up, then medium, then first available)
        best_kf = None
        for cand_shot in reversed(shots_plan):
            cand_path = str(out_dir / f"{cand_shot['shot_id']}_keyframe.jpg")
            if os.path.exists(cand_path) and os.path.getsize(cand_path) > 1000:
                if cand_shot.get("framing") == "hero_close_up" or best_kf is None:
                    best_kf = cand_path
                    if cand_shot.get("framing") == "hero_close_up":
                        break

        thumb_req = ThumbnailGenerationRequest(
            project_id=project_id,
            episode_id=package_id,
            series_title=input_data.title,
            episode_number=1,
            episode_title=input_data.title,
            synopsis=input_data.raw_script_text[:150],
            character_ref_path=best_kf,
            output_dir=str(out_dir / "thumbnails"),
        )
        thumb_res = ThumbnailManager.generate_thumbnails(thumb_req, mock_mode=mock_mode)

        elapsed_ms = int((time.time() - t0) * 1000)

        # Step 7: Complete Provenance & QA report
        progress_emit(run_id, "quality_check", "Extracting representative frames and measuring DINO consistency.", 92)
        dino_results = []
        if input_data.qa_mode == "dino" and not mock_mode:
            from app.core.post.ffmpeg_utils import run_ffmpeg
            from app.core.visual_qa.dino_extractor import DINOExtractor
            extractor = DINOExtractor()
            for shot, clip in zip(shots_plan, shot_clips):
                reference = out_dir / f"{shot['shot_id']}_keyframe.jpg"
                sample = out_dir / f"{shot['shot_id']}_qa_frame.jpg"
                code, _, error = run_ffmpeg([
                    "-y", "-ss", str(max(0.1, shot["duration_s"] / 2)),
                    "-i", clip.video_path, "-frames:v", "1", str(sample),
                ])
                if code:
                    warnings.append(f"DINO frame extraction failed for {shot['shot_id']}: {error[-160:]}")
                    continue
                evaluation = extractor.evaluate_candidates([str(sample)], ref_char_path=str(reference))[0]
                dino_results.append({
                    "shot_id": shot["shot_id"],
                    "frame_path": str(sample),
                    "identity_similarity": evaluation["raw_scores"]["whole_subject_similarity"],
                    "composite_score": evaluation["normalized_scores"]["composite"],
                })
        dino_score = (
            round(sum(item["identity_similarity"] for item in dino_results) / len(dino_results), 4)
            if dino_results else None
        )
        if dino_score is not None and dino_score < 0.65:
            warnings.append(f"DINO visual consistency is low ({dino_score:.3f}); review identity drift.")

        qa_report = {
            "visual_dino_score": dino_score,
            "visual_dino_shots": dino_results,
            "semantic_qa_score": None,
            "continuity_status": "not_evaluated",
            "anatomy_warning": "not_evaluated",
            "overall_decision": "MOCK" if mock_mode else "REVIEW_REQUIRED",
            "warnings": warnings,
            "render_mode": input_data.render_mode,
            "speech_backend": input_data.voice_engine,
            "identity_strategy": "user_reference_image" if reference_image else "shared_keyframe_per_scene",
            "lip_sync": "unavailable_missing_musetalk_weights",
            "quality_profile": input_data.quality_profile,
            "foley_backend": foley_result.backend_used if foley_result else "off",
            "music_backend": input_data.music_engine,
            "upscale_backend": input_data.upscale_engine,
            "frame_interpolation": input_data.frame_interpolation,
        }

        import hashlib
        with open(assembly_res.master_video_path, "rb") as master_file:
            master_sha256 = hashlib.file_digest(master_file, "sha256").hexdigest()
        provenance = {
            "version": "1.1.0",
            "master_sha256": master_sha256,
            "seed": input_data.seed,
            "render_mode": input_data.render_mode,
            "aspect_ratio": input_data.aspect_ratio,
            "quality_profile": input_data.quality_profile,
            "voice_engine": input_data.voice_engine,
            "music_engine": input_data.music_engine,
            "foley_engine": input_data.foley_engine,
            "qa_mode": input_data.qa_mode,
            "frame_interpolation": input_data.frame_interpolation,
            "section_ref": "Master Plan Phase 17 (Creator Mode End-to-End)",
            "pipeline_type": "autonomous_creator_mode_no_manual_graph_editing",
            "package_id": package_id,
            "project_id": project_id,
            "title": input_data.title,
            "target_duration_s": input_data.target_duration_s,
            "actual_duration_s": total_duration,
            "story_beats_count": len(story_beats),
            "shots_count": len(shots_specs),
            "master_video": assembly_res.master_video_path,
            "subtitles_srt": assembly_res.subtitles_path,
            "thumbnails": thumb_res.exported_variants,
            "qa_report": qa_report,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "runtime_ms": elapsed_ms,
        }

        sidecar_path = out_dir / f"{package_id}.provenance.json"
        with open(sidecar_path, "w", encoding="utf-8") as f:
            json.dump(provenance, f, indent=2)

        finish_run(run_id, "completed", f"Render complete in {elapsed_ms / 1000:.1f}s; review is required before publishing.")

        return CreatorPackage(
            project_id=project_id,
            package_id=package_id,
            title=input_data.title,
            master_video_path=assembly_res.master_video_path,
            subtitles_srt_path=assembly_res.subtitles_path or "",
            thumbnail_variants=thumb_res.exported_variants,
            qa_report=qa_report,
            story_beats=story_beats,
            shots_executed=shots_specs,
            audio_summary={
                "dialogue_track": dialogue_wav if speech_ok else None,
                "foley_track": foley_wav if foley_ok else None,
                "music_track": music_wav if music_ok else None,
                "ducking_db": -12.0,
                "loudness_norm": "EBU_R128",
            },
            total_duration_s=total_duration,
            runtime_ms=elapsed_ms,
            provenance_sidecar_path=str(sidecar_path),
        )
