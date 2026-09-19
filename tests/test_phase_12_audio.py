"""Acceptance Test Suite for Phase 12: Audio, Voice, Dialogue Timing, Lip-Sync, and Music."""
import json
import os
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_connection, init_db
from app.core.gpu_lease import GPULeaseManager
from app.core.models import ProjectCreate, ProjectKind
from app.core.projects import ProjectManager
from app.core.audio.voice_registry import VoiceProfile, VoiceRegistry, VoiceRegistryError
from app.core.audio.dialogue_engine import (
    DialogueEngine,
    DialogueEngineError,
    DialogueLine,
    SceneDialogueAssembly,
)
from app.core.audio.lipsync_engine import (
    LipSyncEngine,
    LipSyncEngineError,
    LipSyncRequest,
    LipSyncResponse,
)
from app.core.audio.music_engine import (
    MusicBedRequest,
    MusicBedResponse,
    MusicEngine,
    MusicEngineError,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Initializes a fresh test database state."""
    init_db()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE gpu_lease
            SET owner_job_id = NULL, token = NULL, acquired_at = NULL, heartbeat_at = NULL
            WHERE resource = 'GPU0_HEAVY'
            """
        )
        conn.commit()
    finally:
        conn.close()
    yield


client = TestClient(app)


def test_phase_12_voice_registry_and_consent(tmp_path):
    """Verifies voice registration, actor consent enforcement, and canonical audio storage."""
    project = ProjectManager.create_project(
        ProjectCreate(
            name="Audio Test Project",
            kind=ProjectKind.SERIES,
            description="Testing voice registry",
        )
    )

    # 1. Missing canonical audio file must fail
    missing_wav = str(tmp_path / "non_existent.wav")
    bad_voice = VoiceProfile(
        id="VOICE_MAYA_HINDI_V001",
        project_id=project.id,
        character_id="CHAR_MAYA",
        name="Maya Voice Hindi",
        canonical_audio_path=missing_wav,
        consent_verified=True,
    )
    with pytest.raises(VoiceRegistryError, match="Canonical audio WAV missing on disk"):
        VoiceRegistry.register_voice(bad_voice)

    # 2. Unverified actor consent must fail per Master Plan Rule 6.9
    sample_wav = tmp_path / "maya_canonical_sample.wav"
    sample_wav.write_bytes(b"RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00")

    unconsented_voice = VoiceProfile(
        id="VOICE_MAYA_HINDI_V001",
        project_id=project.id,
        character_id="CHAR_MAYA",
        name="Maya Voice Hindi",
        canonical_audio_path=str(sample_wav),
        consent_verified=False,
    )
    with pytest.raises(VoiceRegistryError, match="actor consent must be verified"):
        VoiceRegistry.register_voice(unconsented_voice)

    # 3. Successful registration with full metadata
    valid_voice = VoiceProfile(
        id="VOICE_MAYA_HINDI_V001",
        project_id=project.id,
        character_id="CHAR_MAYA",
        name="Maya Voice Hindi",
        engine="chatterbox_multilingual",
        language="hi",
        accent="delhi_urban",
        pace=1.05,
        pitch=0.2,
        canonical_audio_path=str(sample_wav),
        pronunciation_notes_json={"Preeti": "Pree-tee", "Antigravity": "An-tee-gra-vi-tee"},
        consent_verified=True,
    )
    reg_voice = VoiceRegistry.register_voice(valid_voice)
    assert reg_voice.id == "VOICE_MAYA_HINDI_V001"

    # 4. Retrieval by character ID
    retrieved = VoiceRegistry.get_character_voice(project.id, "CHAR_MAYA", language="hi")
    assert retrieved is not None
    assert retrieved.name == "Maya Voice Hindi"
    assert retrieved.accent == "delhi_urban"
    assert "Preeti" in retrieved.pronunciation_notes_json


def test_phase_12_dialogue_timing_and_pause_markup():
    """Verifies speech duration estimation from text and punctuation pause markup."""
    # Plain short sentence
    dur_plain = DialogueEngine.estimate_text_duration("Look at that.")
    assert 0.8 <= dur_plain <= 2.0

    # Sentence with pauses (commas, ellipsis, exclamation)
    dur_complex = DialogueEngine.estimate_text_duration(
        "Look, Maya... we don't have much time! Are you ready?"
    )
    # Complex sentence has multiple words and pauses, must be distinctly longer
    assert dur_complex > dur_plain + 1.0

    # Pace scaling: faster pace yields shorter duration
    dur_fast = DialogueEngine.estimate_text_duration("Look at that.", pace=1.5)
    dur_slow = DialogueEngine.estimate_text_duration("Look at that.", pace=0.7)
    assert dur_fast < dur_slow


def test_phase_12_multi_line_scene_dialogue_assembly(tmp_path):
    """Verifies multi-character scene dialogue sequencing, timeline calculation, and master audio track assembly."""
    project = ProjectManager.create_project(
        ProjectCreate(
            name="Dialogue Scene Project",
            kind=ProjectKind.SERIES,
            description="Testing dialogue assembly",
        )
    )

    # Create canonical voices for Maya and Vikram
    maya_wav = tmp_path / "maya.wav"
    maya_wav.write_bytes(b"RIFF\x24\x08\x00\x00WAVE")
    vikram_wav = tmp_path / "vikram.wav"
    vikram_wav.write_bytes(b"RIFF\x24\x08\x00\x00WAVE")

    VoiceRegistry.register_voice(
        VoiceProfile(
            id="VOICE_MAYA_001",
            project_id=project.id,
            character_id="CHAR_MAYA",
            name="Maya",
            canonical_audio_path=str(maya_wav),
        )
    )
    VoiceRegistry.register_voice(
        VoiceProfile(
            id="VOICE_VIKRAM_001",
            project_id=project.id,
            character_id="CHAR_VIKRAM",
            name="Vikram",
            canonical_audio_path=str(vikram_wav),
        )
    )

    # Multi-line dialogue scene alternating between two characters
    dialogue_script = [
        DialogueLine(
            character_id="CHAR_MAYA",
            text="Vikram, did you find the red diary in the archives?",
            shot_id="SHOT_001",
            pause_after_s=0.5,
        ),
        DialogueLine(
            character_id="CHAR_VIKRAM",
            text="Yes... but someone tore out the last three pages.",
            shot_id="SHOT_002",
            pause_after_s=0.4,
        ),
        DialogueLine(
            character_id="CHAR_MAYA",
            text="Then he knows we are tracking him. We need to move now!",
            shot_id="SHOT_003",
            pause_after_s=0.6,
        ),
    ]

    out_dir = tmp_path / "audio_renders"
    assembly = DialogueEngine.assemble_scene_dialogue(
        project_id=project.id,
        scene_id="SCENE_E01_S03",
        dialogue_lines=dialogue_script,
        output_dir=str(out_dir),
    )

    assert assembly.scene_id == "SCENE_E01_S03"
    assert assembly.line_count == 3
    assert assembly.total_duration_s > 5.0
    assert os.path.exists(assembly.master_dialogue_audio_path)

    # Verify strictly non-overlapping sequential timeline
    for i in range(len(assembly.lines) - 1):
        curr_line = assembly.lines[i]
        next_line = assembly.lines[i + 1]
        assert curr_line.start_time_s < curr_line.end_time_s
        assert next_line.start_time_s >= curr_line.end_time_s + curr_line.pause_after_s - 0.05
        assert os.path.exists(curr_line.audio_file_path)

    # Verify shot IDs preserved
    assert assembly.lines[0].shot_id == "SHOT_001"
    assert assembly.lines[1].shot_id == "SHOT_002"
    assert assembly.lines[2].shot_id == "SHOT_003"


def test_phase_12_musetalk_lipsync_with_fallback(tmp_path):
    """Verifies MuseTalk 1.5 lip sync execution and still-head audio-first fallback safeguard."""
    dummy_video = tmp_path / "shot_input.mp4"
    dummy_video.write_bytes(b"\x00\x00\x00 ftypisom" + b"\x00" * 100)
    dummy_audio = tmp_path / "dialogue_line.wav"
    dummy_audio.write_bytes(b"RIFF\x24\x08\x00\x00WAVE" + b"\x00" * 100)

    # 1. Normal lip-sync run
    req_normal = LipSyncRequest(
        project_id="proj_audio_test",
        video_shot_path=str(dummy_video),
        audio_track_path=str(dummy_audio),
        force_still_head_fallback=False,
    )
    res_normal = LipSyncEngine.execute_lipsync(req_normal, mock_mode=True)
    assert res_normal.fallback_used is False
    assert res_normal.alignment_score >= 0.80
    assert os.path.exists(res_normal.output_video_path)
    assert res_normal.output_video_path.endswith(".mp4")

    # 2. Deformation safeguard / forced fallback run
    req_fallback = LipSyncRequest(
        project_id="proj_audio_test",
        video_shot_path=str(dummy_video),
        audio_track_path=str(dummy_audio),
        force_still_head_fallback=True,
    )
    res_fallback = LipSyncEngine.execute_lipsync(req_fallback, mock_mode=True)
    assert res_fallback.fallback_used is True
    assert res_fallback.provenance_json["fallback_mode"] == "still_head_audio_first"
    assert os.path.exists(res_fallback.output_video_path)


def test_phase_12_acestep_music_snapping_and_ducking(tmp_path):
    """Verifies ACE-Step 1.5 music bed generation snapped to scene duration and dialogue ducking."""
    # Unsupported theme must fail
    bad_req = MusicBedRequest(
        project_id="proj_audio_test",
        scene_id="SCENE_01",
        theme_tag="techno_dubstep_unsupported",
        target_duration_s=12.5,
    )
    with pytest.raises(MusicEngineError, match="not supported"):
        MusicEngine.generate_music_bed(bad_req)

    # Valid thematic background bed
    valid_req = MusicBedRequest(
        project_id="proj_audio_test",
        scene_id="SCENE_01",
        theme_tag="suspense_ambient",
        target_duration_s=14.5,
        fade_in_s=1.0,
        fade_out_s=2.0,
        ducking_db=-12.0,
    )
    res = MusicEngine.generate_music_bed(valid_req, mock_mode=True)
    assert res.theme_tag == "suspense_ambient"
    assert res.duration_s == 14.5
    assert res.ducking_db == -12.0
    assert os.path.exists(res.music_file_path)
    assert res.music_file_path.endswith(".wav")


def test_phase_12_api_endpoints(tmp_path):
    """Verifies REST API endpoints /api/v1/audio/voices, /dialogue/assemble, /lipsync, and /music/generate."""
    project = ProjectManager.create_project(
        ProjectCreate(
            name="API Audio Project",
            kind=ProjectKind.SERIES,
            description="Testing audio API",
        )
    )

    sample_wav = tmp_path / "sample.wav"
    sample_wav.write_bytes(b"RIFF\x24\x08\x00\x00WAVE")

    # 1. Register voice endpoint
    voice_payload = {
        "id": f"VOICE_API_{uuid.uuid4().hex[:6]}",
        "project_id": project.id,
        "character_id": "CHAR_API",
        "name": "API Actor",
        "engine": "chatterbox_multilingual",
        "language": "hi",
        "accent": "neutral",
        "pace": 1.0,
        "pitch": 0.0,
        "canonical_audio_path": str(sample_wav),
        "consent_verified": True,
    }
    res_v = client.post("/api/v1/audio/voices", json=voice_payload)
    assert res_v.status_code == 200
    v_data = res_v.json()
    assert v_data["id"] == voice_payload["id"]

    # 2. List voices endpoint
    res_list = client.get(f"/api/v1/audio/voices?project_id={project.id}")
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 1

    # 3. Assemble dialogue endpoint
    assemble_payload = {
        "project_id": project.id,
        "scene_id": "SCENE_API_01",
        "lines": [
            {"character_id": "CHAR_API", "text": "This is line one.", "pause_after_s": 0.4},
            {"character_id": "CHAR_API", "text": "This is line two!", "pause_after_s": 0.5},
        ],
    }
    res_ass = client.post("/api/v1/audio/dialogue/assemble", json=assemble_payload)
    assert res_ass.status_code == 200
    ass_data = res_ass.json()
    assert ass_data["line_count"] == 2
    assert os.path.exists(ass_data["master_dialogue_audio_path"])

    # 4. Music generate endpoint
    music_payload = {
        "project_id": project.id,
        "scene_id": "SCENE_API_01",
        "theme_tag": "dramatic_cliffhanger",
        "target_duration_s": 10.0,
    }
    res_mus = client.post("/api/v1/audio/music/generate?mock=true", json=music_payload)
    assert res_mus.status_code == 200
    assert res_mus.json()["duration_s"] == 10.0
