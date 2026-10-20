"""Narrated-story acceptance: literal text, real WAV timing and safe assembly."""
import io
import wave

import pytest
from fastapi.testclient import TestClient

from app.core import storyboard as sb
from app.core.audio import speech_synth
from app.core.config import settings
from app.core.database import init_db
from app.core.narration import plan_narration
from app.core.post.assembly_engine import AssemblyEngine, AssemblyEngineError, AssemblyRequest, ShotClipInput
from app.main import app


def recording(seconds=1, rate=8000):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x01\x00" * int(seconds * rate))
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def isolated_studio(tmp_path, monkeypatch):
    monkeypatch.setattr(settings.paths, "database", str(tmp_path / "studio.db"))
    monkeypatch.setattr(sb, "ROOT", tmp_path)
    init_db()
    sb.ensure_tables()


def make_board(language="en", text="She opened the letter.\n\nThe date was tomorrow."):
    return sb.create_storyboard("Tomorrow's Letter", text, {"input_mode": "narration", "voice_language": language}, target_duration_s=4)


@pytest.mark.parametrize("language,text", [
    ("en", 'Priya read: "Wait for me."\n\nAarav was already outside.'),
    ("hi", 'प्रिया ने चिट्ठी पढ़ी: "मेरा इंतज़ार करना।"\n\nआरव दरवाज़े पर था।'),
    ("hi", 'Priya ne letter padha: "Mera intezaar karna."\n\nAarav darwaaze par tha.'),
])
def test_narration_is_spoken_verbatim_in_source_order(language, text):
    board = make_board(language, text)
    assert " ".join(s["dialogue"] for s in board["shots"]) == " ".join(text.split())
    assert all(s["speaker"] == "NARRATOR" and s["engine"] == "2.5d" for s in board["shots"])
    assert board["settings"]["voice_language"] == language
    assert board["shots"][0]["keyframe_source"] == "flux"


def test_long_paragraph_splits_without_dropping_words():
    text = ('"Will you come back?" she asked. ' * 60).strip()
    shots = plan_narration(text, 60)
    assert len(shots) > 4
    assert all(0 < len(s["dialogue_line"]) <= 240 for s in shots)
    assert " ".join(s["dialogue_line"] for s in shots) == text
    assert sum(s["duration_s"] for s in shots) == pytest.approx(60)


def test_recording_uses_measured_duration_above_old_twelve_second_limit():
    board = make_board()
    shot = board["shots"][0]
    candidate = sb.import_speech(shot["id"], recording(16))
    fresh = sb.get_shot(shot["id"])
    assert candidate["duration_s"] == 16
    assert fresh["duration_s"] == pytest.approx(16.6)
    assert fresh["selected_speech_id"] == candidate["id"]
    assert candidate["provenance"]["language"] == "en"


@pytest.mark.parametrize("contents", [b"not a wav", recording(1)[:-20], recording(121), b""])
def test_malformed_or_excessive_recording_rejected(contents):
    shot = make_board()["shots"][0]
    with pytest.raises(sb.StoryboardError):
        sb.import_speech(shot["id"], contents)
    assert not sb.get_shot(shot["id"])["selected_speech_id"]


def test_upload_endpoint_validates_file_and_preserves_hindi():
    client = TestClient(app)
    response = client.post("/api/v1/storyboards", json={"title": "चिट्ठी", "script_text": "आरव दरवाज़े पर था।",
        "settings": {"input_mode": "narration", "voice_language": "hi"}, "target_duration_s": 4})
    assert response.status_code == 200
    shot = response.json()["shots"][0]
    url = f"/api/v1/storyboards/shots/{shot['id']}/speech/upload"
    assert client.post(url, files={"file": ("voice.mp3", b"fake", "audio/mpeg")}).status_code == 400
    assert client.post(url, files={"file": ("voice.wav", b"fake", "audio/wav")}).status_code == 400
    uploaded = client.post(url, files={"file": ("voice.wav", recording(2), "audio/wav")})
    assert uploaded.status_code == 200
    assert uploaded.json()["prompt"] == "आरव दरवाज़े पर था।"
    assert uploaded.json()["duration_s"] == 2


def test_transcript_and_voice_changes_invalidate_audio_and_motion(tmp_path):
    board = make_board()
    shot = board["shots"][0]
    candidate = sb.import_speech(shot["id"], recording())
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"test candidate")
    sb.add_candidate(shot["id"], "clip", str(clip), duration_s=4, select=True)
    fresh = sb.update_shot(shot["id"], {"dialogue": "The letter was blank."})
    assert fresh["selected_speech_id"] is None and fresh["selected_clip_id"] is None
    with pytest.raises(sb.StoryboardError, match="older line"):
        sb.select_candidate(candidate["id"])
    candidate = sb.import_speech(shot["id"], recording())
    fresh = sb.update_storyboard(board["id"], {"settings": {"voice_language": "hi"}})
    assert fresh["shots"][0]["selected_speech_id"] is None
    with pytest.raises(sb.StoryboardError, match="different narration language"):
        sb.select_candidate(candidate["id"])


def test_narrator_name_persists_when_installed_voice_order_changes(monkeypatch):
    board = make_board("hi")
    voices = [{"name": "Hindi B", "language": "hi-IN"}, {"name": "English", "language": "en-US"}]
    monkeypatch.setattr(speech_synth, "list_speech_voices", lambda: voices)
    calls = []
    def synth(text, path, **kwargs):
        calls.append(kwargs)
        from pathlib import Path
        Path(path).write_bytes(recording())
        return True
    monkeypatch.setattr(speech_synth, "synthesize_speech", synth)
    sb.handle_speech("voice-test-1", {"storyboard_id": board["id"]})
    voices.insert(0, {"name": "Hindi A", "language": "hi-IN"})
    sb.handle_speech("voice-test-2", {"storyboard_id": board["id"]})
    assert {call["voice_name"] for call in calls} == {"Hindi B"}
    assert {call["language"] for call in calls} == {"hi"}
    assert sb.get_storyboard(board["id"])["settings"]["voice_name"] == "Hindi B"


def test_missing_hindi_voice_fails_before_synthesis(monkeypatch):
    board = make_board("hi")
    monkeypatch.setattr(speech_synth, "list_speech_voices", lambda: [{"name": "English", "language": "en-US"}])
    def must_not_run(*args, **kwargs):
        pytest.fail("Wrong-language synthesis attempted")
    monkeypatch.setattr(speech_synth, "synthesize_speech", must_not_run)
    with pytest.raises(sb.StoryboardError, match="No matching Windows voice"):
        sb.handle_speech("voice-missing", {"storyboard_id": board["id"]})


def test_missing_only_batch_and_automatic_voice_preserve_approved_recording(tmp_path, monkeypatch):
    board = make_board()
    first, second = board["shots"]
    recording_candidate = sb.import_speech(first["id"], recording())
    clip_path = tmp_path / "approved.mp4"
    clip_path.write_bytes(b"approved clip")
    clip_candidate = sb.add_candidate(first["id"], "clip", str(clip_path), duration_s=4, select=True)
    monkeypatch.setattr(speech_synth, "list_speech_voices", lambda: [{"name": "English", "language": "en-US"}])
    spoken = []
    def synth(text, path, **kwargs):
        from pathlib import Path
        spoken.append(text)
        Path(path).write_bytes(recording())
        return True
    monkeypatch.setattr(speech_synth, "synthesize_speech", synth)
    response = TestClient(app).post(f"/api/v1/storyboards/{board['id']}/batch", json={
        "keyframes": False, "clips": False, "speech": True, "only_missing": True})
    assert response.status_code == 200
    job = response.json()["jobs"][0]
    assert job["payload_json"]["only_missing"] is True
    sb.handle_speech(job["id"], job["payload_json"])
    assert spoken == [second["dialogue"]]
    fresh = sb.get_shot(first["id"])
    assert fresh["selected_speech_id"] == recording_candidate["id"]
    assert fresh["selected_clip_id"] == clip_candidate["id"]


def test_assembly_rejects_missing_narration_and_short_clip(tmp_path):
    board = make_board(text="The date was tomorrow.")
    shot = board["shots"][0]
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"test candidate")
    sb.add_candidate(shot["id"], "clip", str(path), duration_s=4, select=True)
    with pytest.raises(sb.StoryboardError, match="Generate or upload narration"):
        sb.handle_assemble("missing-audio", {"storyboard_id": board["id"]})
    sb.import_speech(shot["id"], recording(5))
    sb.add_candidate(shot["id"], "clip", str(path), duration_s=4, select=True)
    with pytest.raises(sb.StoryboardError, match="shorter than its narration"):
        sb.handle_assemble("short-clip", {"storyboard_id": board["id"]})


def test_ffmpeg_failure_does_not_report_success_or_drop_narration(tmp_path, monkeypatch):
    from app.core.post import assembly_engine
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"input")
    calls = []
    def failed(*args, **kwargs):
        calls.append(args)
        return 1, "", "No such filter: subtitles"
    monkeypatch.setattr(assembly_engine, "run_ffmpeg", failed)
    with pytest.raises(AssemblyEngineError, match="No such filter: subtitles"):
        AssemblyEngine.assemble(AssemblyRequest(project_id="test", sequence_id="test",
            shots=[ShotClipInput(shot_id="1", video_path=str(clip), out_trim_s=4)], output_dir=str(tmp_path)))
    assert len(calls) == 1
    assert not list(tmp_path.glob("*.provenance.json"))


@pytest.mark.parametrize("settings_patch", [{"input_mode": "unknown"}, {"voice_language": "fr"}, {"voice_name": []}])
def test_invalid_narration_settings_are_rejected(settings_patch):
    with pytest.raises(sb.StoryboardError):
        sb.create_storyboard("Invalid", "Text", settings_patch)
