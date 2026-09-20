"""Storyboard domain tests: planning, editing, candidates and selection (no GPU)."""
from pathlib import Path

import pytest
from PIL import Image

from app.core import storyboard as sb
from app.core.asset_factory import AssetFactory
from app.core.database import init_db
from app.core.models import AssetKind

SCRIPT = (
    "SCENE 1: EXT. NEO-MUMBAI RAINY STREET - NIGHT\n"
    "Diya walks down the alley checking her wrist display.\n\n"
    "DIYA\nThe transmission is locked. We have under a minute.\n\n"
    "SCENE 2: INT. SAFEHOUSE - CONTINUOUS\n"
    "Kabir slams the door and kills the lights."
)


@pytest.fixture(scope="module", autouse=True)
def _db():
    init_db()
    sb.ensure_tables()


@pytest.fixture
def board():
    created = sb.create_storyboard("Storyboard Test", SCRIPT, {"quality_profile": "draft"}, target_duration_s=12)
    yield created
    sb.delete_storyboard(created["id"])


def test_plan_creates_ordered_shots_with_inheritance(board):
    shots = board["shots"]
    assert len(shots) >= 3
    assert [s["position"] for s in shots] == list(range(1, len(shots) + 1))
    assert shots[0]["keyframe_source"] == "flux"
    dialogue = [s for s in shots if s["dialogue"]]
    assert dialogue and dialogue[0]["speaker"] == "DIYA"
    # A later shot in the same beat inherits; a new scene starts fresh.
    same_beat = [s for s in shots[1:] if s["heading"] == shots[0]["heading"]]
    assert all(s["keyframe_source"] == "inherit" for s in same_beat)
    new_scene = [s for s in shots if s["heading"] != shots[0]["heading"]]
    assert new_scene and new_scene[0]["keyframe_source"] == "flux"


def test_edit_reorder_add_delete(board):
    first, second = board["shots"][0], board["shots"][1]
    updated = sb.update_shot(first["id"], {"engine": "2.5d", "camera_motion": "pan_left", "duration_s": 3.25, "action": "New action"})
    assert (updated["engine"], updated["camera_motion"], updated["duration_s"], updated["action"]) == ("2.5d", "pan_left", 3.25, "New action")
    with pytest.raises(sb.StoryboardError):
        sb.update_shot(first["id"], {"engine": "nonsense"})

    ids = [s["id"] for s in board["shots"]]
    ids[0], ids[1] = ids[1], ids[0]
    reordered = sb.reorder_shots(board["id"], ids)
    assert reordered["shots"][0]["id"] == second["id"] and reordered["shots"][0]["position"] == 1

    added = sb.add_shot(board["id"], after_shot_id=second["id"], action="Insert shot")
    fresh = sb.get_storyboard(board["id"])
    assert fresh["shots"][1]["id"] == added["id"]
    assert [s["position"] for s in fresh["shots"]] == list(range(1, len(fresh["shots"]) + 1))

    sb.delete_shot(added["id"])
    fresh = sb.get_storyboard(board["id"])
    assert added["id"] not in {s["id"] for s in fresh["shots"]}
    assert [s["position"] for s in fresh["shots"]] == list(range(1, len(fresh["shots"]) + 1))


def test_candidate_from_asset_selects_and_invalidates_clip(board, tmp_path):
    shot = board["shots"][0]
    image = tmp_path / "ref.png"
    Image.new("RGB", (640, 360), (200, 40, 40)).save(image)
    asset = AssetFactory().create_asset(project_id="LIBRARY", asset_id=f"TEST_{shot['id']}", kind=AssetKind.UPLOADED.value,
                                        name="ref.png", file_path=str(image))
    cand = sb.candidate_from_asset(shot["id"], asset.id)
    refreshed = sb.get_shot(shot["id"])
    assert refreshed["selected_keyframe_id"] == cand["id"]
    fitted = Image.open(cand["file_path"])
    assert fitted.size == sb.ASPECTS[board["settings"]["aspect_ratio"]]

    clip = sb.add_candidate(shot["id"], "clip", str(image), engine="2.5d", duration_s=4.0, select=True)
    assert sb.get_shot(shot["id"])["selected_clip_id"] == clip["id"]
    sb.update_shot(shot["id"], {"action": "changed"})
    assert sb.get_shot(shot["id"])["selected_clip_id"] is None
    assert sb.get_shot(shot["id"])["selected_keyframe_id"] == cand["id"]

    second = sb.add_candidate(shot["id"], "keyframe", str(image), engine="test")
    sb.select_candidate(second["id"])
    assert sb.get_shot(shot["id"])["selected_keyframe_id"] == second["id"]


def test_resolve_engine_routes_dialogue_and_risky_motion_to_25d():
    engines = {"2.5d": {"available": True}, "ltx": {"available": True}, "h3": {"available": False}, "scail": {"available": False}}
    assert sb.resolve_engine({"engine": "auto", "action": "Rain falls on the street", "dialogue": ""}, engines) == "ltx"
    assert sb.resolve_engine({"engine": "auto", "action": "She holds the phone", "dialogue": ""}, engines) == "2.5d"
    assert sb.resolve_engine({"engine": "auto", "action": "Rain", "dialogue": "Hello"}, engines) == "2.5d"
    assert sb.resolve_engine({"engine": "ltx", "action": "x", "dialogue": "Hello"}, engines) == "ltx"
    with pytest.raises(sb.StoryboardError):
        sb.resolve_engine({"engine": "h3", "action": "x", "dialogue": ""}, engines)
