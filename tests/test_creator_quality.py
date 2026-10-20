import wave
from pathlib import Path
from unittest.mock import patch
import pytest
from app.core.creator_mode import CreatorModeEngine, CreatorModeError, CreatorScriptInput
from app.core.audio.speech_synth import assemble_speech_timeline, synthesize_speech
from app.core.local_video import build_workflow


def test_shot_plan_preserves_all_speech_and_source_action():
    script = 'SCENE 1: FIELD - DAY\nA farmer lifts a basket.\nMAYA: Good morning.\nRAJ: The harvest is ready.\nMAYA: Let us begin.'
    beats = CreatorModeEngine.normalize_story_beats(script, 15)
    shots = CreatorModeEngine.plan_shots(beats)
    assert [s['dialogue_line'] for s in shots] == ['Good morning.', 'The harvest is ready.', 'Let us begin.']
    assert all(s['action'] == 'A farmer lifts a basket.' for s in shots)
    assert sum(s['duration_s'] for s in shots) == 15


def test_blank_script_rejected():
    with pytest.raises(CreatorModeError):
        CreatorModeEngine.normalize_story_beats('   ')


def test_no_invented_character_for_landscape():
    assert CreatorModeEngine.normalize_story_beats('A river flows through green fields.')[0].characters == []


def test_speech_failure_is_not_a_tone(tmp_path):
    with patch('app.core.audio.speech_synth.subprocess.run', side_effect=OSError('offline engine unavailable')):
        assert not synthesize_speech('Hello', str(tmp_path / 'speech.wav'))
    assert not (tmp_path / 'speech.wav').exists()


def test_speech_starts_with_its_shot_and_keeps_duration(tmp_path):
    source = tmp_path / 'line.wav'
    with wave.open(str(source), 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
        wav.writeframes(b'\x00\x10' * 12000)
    dest = tmp_path / 'master.wav'
    assert assemble_speech_timeline([{'duration_s': 2}, {'duration_s': 2, 'speech_path': str(source)}], str(dest), 4)
    with wave.open(str(dest), 'rb') as wav:
        assert wav.getnframes() == 96000
        data = wav.readframes(wav.getnframes())
    assert not any(data[:round(2.3*24000)*2])
    assert any(data[round(2.3*24000)*2:round(2.8*24000)*2])
    assert not any(data[round(2.8*24000)*2:])


def test_ltx_workflow_matches_official_image_to_video_chain():
    workflow = build_workflow('image.png', 'A farmer moves.', 480, 832, 97, 42)
    # Source frame is preprocessed, then pinned at frame 0 with full strength.
    assert workflow['13']['class_type'] == 'LTXVPreprocess'
    assert workflow['13']['inputs']['image'] == ['5', 0]
    assert workflow['6']['class_type'] == 'LTXVAddGuide'
    assert workflow['6']['inputs']['image'] == ['13', 0]
    assert workflow['6']['inputs']['frame_idx'] == 0
    assert workflow['6']['inputs']['strength'] == 1.0
    assert workflow['10']['class_type'] == 'SamplerCustom'
    assert workflow['10']['inputs']['noise_seed'] == 42
    # The guide frame is cropped off before decoding.
    assert workflow['15']['class_type'] == 'LTXVCropGuides'
    assert workflow['11']['inputs']['samples'] == ['15', 2]


def test_flux_templates_use_distilled_model_settings():
    # flux-2-klein-4b-fp8 is step-distilled: the official template uses CFG 1 and 4 steps.
    import json
    templates = sorted((Path(__file__).resolve().parents[1] / 'workflows' / 'api_format').glob('flux_*.json'))
    assert templates
    for path in templates:
        workflow = json.loads(path.read_text(encoding='utf-8'))
        assert [n['inputs']['cfg'] for n in workflow.values() if n['class_type'] == 'CFGGuider'] == [1.0], path.name
        assert [n['inputs']['steps'] for n in workflow.values() if n['class_type'] == 'Flux2Scheduler'] == [4], path.name


def test_real_keyframe_failure_stops_pipeline(tmp_path):
    with patch('app.core.creator_mode.render_cinematic_keyframe', side_effect=RuntimeError('model unavailable')):
        with pytest.raises(CreatorModeError, match='model unavailable'):
            CreatorModeEngine.execute_pipeline(CreatorScriptInput(raw_script_text='A river flows.', target_duration_s=4), mock_mode=False)
