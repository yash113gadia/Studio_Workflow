"""Shot-level storyboard: persistent, granular Creator workflow.

A storyboard is a script broken into editable shots. Every shot owns keyframe,
clip and speech candidates; the user (or auto mode) selects one of each, then
the storyboard is assembled into a master. Long operations run as durable jobs
handled by app.core.worker.
"""
from __future__ import annotations

import json
import os
import shutil
import time
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageOps

from app.core.asset_factory import AssetFactory
from app.core.capabilities import discover_capabilities
from app.core.database import get_connection
from app.core.models import AssetKind, JobCreate, JobKind, ProjectCreate, ProjectKind
from app.core.projects import ProjectManager
from app.core.queue import DurableQueue
from app.core.run_progress import emit as progress_emit

ROOT = Path(__file__).resolve().parents[2]

ENGINES = ("auto", "2.5d", "ltx", "h3", "scail")
CAMERA_MOTIONS = ("push_in", "pull_out", "pan_left", "pan_right", "tilt_up", "tilt_down", "static")
FRAMINGS = ("wide_establishing", "medium", "medium_close_up", "hero_close_up", "dramatic_push_insert", "wide_dynamic")
KEYFRAME_SOURCES = ("flux", "reference", "inherit")
ASPECTS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}

DEFAULT_SETTINGS = {
    "aspect_ratio": "9:16",
    "genre": "cyberpunk_thriller",
    "quality_profile": "balanced",
    "seed": 42,
    "style_prompt": "",
    "voice_engine": "windows_sapi",
    "music_engine": "off",
    "foley_engine": "library",
    "qa_mode": "dino",
    "frame_interpolation": "off",
    "burn_subtitles": True,
    "keyframe_candidates": 2,
}


class StoryboardError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sb_id() -> str:
    return f"sb_{uuid.uuid4().hex[:12]}"


def ensure_tables() -> None:
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS storyboards (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                title TEXT NOT NULL,
                script_text TEXT NOT NULL,
                settings_json TEXT DEFAULT '{}',
                status TEXT DEFAULT 'DRAFT',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS storyboard_shots (
                id TEXT PRIMARY KEY,
                storyboard_id TEXT NOT NULL,
                position INTEGER NOT NULL,
                label TEXT NOT NULL,
                heading TEXT DEFAULT '',
                action TEXT DEFAULT '',
                speaker TEXT DEFAULT '',
                dialogue TEXT DEFAULT '',
                framing TEXT DEFAULT 'medium',
                duration_s REAL DEFAULT 5.0,
                engine TEXT DEFAULT 'auto',
                camera_motion TEXT DEFAULT 'push_in',
                seed INTEGER,
                keyframe_source TEXT DEFAULT 'flux',
                reference_asset_id TEXT,
                selected_keyframe_id TEXT,
                selected_clip_id TEXT,
                selected_speech_id TEXT,
                status TEXT DEFAULT 'PLANNED',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (storyboard_id) REFERENCES storyboards(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS shot_candidates (
                id TEXT PRIMARY KEY,
                shot_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                file_path TEXT NOT NULL,
                engine TEXT DEFAULT '',
                seed INTEGER,
                prompt TEXT DEFAULT '',
                duration_s REAL,
                scores_json TEXT DEFAULT '{}',
                provenance_json TEXT DEFAULT '{}',
                asset_id TEXT,
                job_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (shot_id) REFERENCES storyboard_shots(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS storyboard_renders (
                id TEXT PRIMARY KEY,
                storyboard_id TEXT NOT NULL,
                master_video_path TEXT NOT NULL,
                srt_path TEXT,
                thumbnails_json TEXT DEFAULT '[]',
                qa_json TEXT DEFAULT '{}',
                provenance_json TEXT DEFAULT '{}',
                settings_json TEXT DEFAULT '{}',
                duration_s REAL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (storyboard_id) REFERENCES storyboards(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_sb_shots ON storyboard_shots(storyboard_id, position);
            CREATE INDEX IF NOT EXISTS idx_shot_candidates ON shot_candidates(shot_id, kind);
            """
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------------

def _row(row) -> Dict[str, Any]:
    return dict(row) if row is not None else None


def _json(value: Optional[str]) -> Any:
    try:
        return json.loads(value) if value else {}
    except ValueError:
        return {}


def _shot_dir(storyboard: Dict[str, Any], shot_id: str) -> Path:
    path = ROOT / "projects" / storyboard["project_id"] / "storyboards" / storyboard["id"] / "shots" / shot_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _storyboard_dir(storyboard: Dict[str, Any]) -> Path:
    path = ROOT / "projects" / storyboard["project_id"] / "storyboards" / storyboard["id"]
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def create_storyboard(
    title: str,
    script_text: str,
    settings: Optional[Dict[str, Any]] = None,
    project_id: Optional[str] = None,
    target_duration_s: float = 30.0,
) -> Dict[str, Any]:
    from app.core.creator_mode import CreatorModeEngine

    merged = {**DEFAULT_SETTINGS, **(settings or {})}
    if merged["aspect_ratio"] not in ASPECTS:
        raise StoryboardError(f"Unsupported aspect ratio {merged['aspect_ratio']}")
    if not project_id:
        project = ProjectManager.create_project(ProjectCreate(name=title, kind=ProjectKind.CREATOR, description="Storyboard project"))
        project_id = project.id

    beats = CreatorModeEngine.normalize_story_beats(script_text, target_duration_s)
    plan = CreatorModeEngine.plan_shots(beats)

    sb_id = _sb_id()
    now = _now()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO storyboards (id, project_id, title, script_text, settings_json, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (sb_id, project_id, title, script_text, json.dumps(merged), "DRAFT", now, now),
        )
        for position, shot in enumerate(plan, start=1):
            conn.execute(
                """INSERT INTO storyboard_shots
                   (id, storyboard_id, position, label, heading, action, speaker, dialogue, framing, duration_s,
                    engine, camera_motion, seed, keyframe_source, status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    f"shot_{uuid.uuid4().hex[:10]}", sb_id, position, shot["shot_id"], shot["heading"], shot["action"],
                    shot.get("speaker") or "", shot.get("dialogue_line") or "", shot["framing"],
                    round(float(shot["duration_s"]), 2), "auto", "push_in", None,
                    "inherit" if position > 1 and shot["beat_number"] == plan[position - 2]["beat_number"] else "flux",
                    "PLANNED", now, now,
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return get_storyboard(sb_id)


def list_storyboards(project_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        query = "SELECT s.*, (SELECT COUNT(*) FROM storyboard_shots WHERE storyboard_id = s.id) AS shot_count FROM storyboards s"
        params: List[Any] = []
        if project_id:
            query += " WHERE project_id = ?"
            params.append(project_id)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        out = []
        for row in rows:
            item = _row(row)
            item["settings"] = _json(item.pop("settings_json"))
            latest = conn.execute(
                "SELECT master_video_path, thumbnails_json FROM storyboard_renders WHERE storyboard_id = ? ORDER BY created_at DESC LIMIT 1",
                (item["id"],),
            ).fetchone()
            item["latest_render"] = _row(latest)
            if item["latest_render"]:
                item["latest_render"]["thumbnails"] = _json(item["latest_render"].pop("thumbnails_json")) or []
            out.append(item)
        return out
    finally:
        conn.close()


def get_storyboard(sb_id: str) -> Dict[str, Any]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM storyboards WHERE id = ?", (sb_id,)).fetchone()
        if not row:
            raise StoryboardError(f"Storyboard not found: {sb_id}")
        board = _row(row)
        board["settings"] = {**DEFAULT_SETTINGS, **_json(board.pop("settings_json"))}
        shots = [_row(r) for r in conn.execute(
            "SELECT * FROM storyboard_shots WHERE storyboard_id = ? ORDER BY position", (sb_id,)
        ).fetchall()]
        for shot in shots:
            cands = [_row(r) for r in conn.execute(
                "SELECT * FROM shot_candidates WHERE shot_id = ? ORDER BY created_at DESC", (shot["id"],)
            ).fetchall()]
            for cand in cands:
                cand["scores"] = _json(cand.pop("scores_json"))
                cand["provenance"] = _json(cand.pop("provenance_json"))
            shot["candidates"] = cands
        board["shots"] = shots
        renders = [_row(r) for r in conn.execute(
            "SELECT * FROM storyboard_renders WHERE storyboard_id = ? ORDER BY created_at DESC", (sb_id,)
        ).fetchall()]
        for render in renders:
            render["thumbnails"] = _json(render.pop("thumbnails_json")) or []
            render["qa"] = _json(render.pop("qa_json"))
            render["provenance"] = _json(render.pop("provenance_json"))
            render["settings"] = _json(render.pop("settings_json"))
        board["renders"] = renders
        board["jobs"] = [job.model_dump() for job in DurableQueue.list_jobs(project_id=board["project_id"], limit=200)
                         if (job.payload_json or {}).get("storyboard_id") == sb_id]
        return board
    finally:
        conn.close()


def get_shot(shot_id: str) -> Dict[str, Any]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM storyboard_shots WHERE id = ?", (shot_id,)).fetchone()
        if not row:
            raise StoryboardError(f"Shot not found: {shot_id}")
        return _row(row)
    finally:
        conn.close()


def update_storyboard(sb_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    board = get_storyboard(sb_id)
    conn = get_connection()
    try:
        title = patch.get("title", board["title"])
        settings = {**board["settings"], **(patch.get("settings") or {})}
        conn.execute(
            "UPDATE storyboards SET title = ?, settings_json = ?, updated_at = ? WHERE id = ?",
            (title, json.dumps(settings), _now(), sb_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_storyboard(sb_id)


SHOT_EDITABLE = {
    "heading", "action", "speaker", "dialogue", "framing", "duration_s", "engine", "camera_motion",
    "seed", "keyframe_source", "reference_asset_id", "selected_keyframe_id", "selected_clip_id",
    "selected_speech_id", "notes", "label",
}


def update_shot(shot_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    shot = get_shot(shot_id)
    fields = {k: v for k, v in patch.items() if k in SHOT_EDITABLE}
    if "engine" in fields and fields["engine"] not in ENGINES:
        raise StoryboardError(f"Unknown engine {fields['engine']}")
    if "camera_motion" in fields and fields["camera_motion"] not in CAMERA_MOTIONS:
        raise StoryboardError(f"Unknown camera motion {fields['camera_motion']}")
    if "keyframe_source" in fields and fields["keyframe_source"] not in KEYFRAME_SOURCES:
        raise StoryboardError(f"Unknown keyframe source {fields['keyframe_source']}")
    if "duration_s" in fields:
        fields["duration_s"] = max(1.0, min(12.0, float(fields["duration_s"])))
    if not fields:
        return shot
    # Any creative change invalidates the rendered clip, not the keyframe.
    if any(k in fields for k in ("action", "engine", "camera_motion", "duration_s", "selected_keyframe_id")):
        fields.setdefault("selected_clip_id", None)
    if "dialogue" in fields or "speaker" in fields:
        fields.setdefault("selected_speech_id", None)
    fields["updated_at"] = _now()
    assignments = ", ".join(f"{k} = ?" for k in fields)
    conn = get_connection()
    try:
        conn.execute(f"UPDATE storyboard_shots SET {assignments} WHERE id = ?", (*fields.values(), shot_id))
        conn.execute("UPDATE storyboards SET updated_at = ? WHERE id = ?", (_now(), shot["storyboard_id"]))
        conn.commit()
    finally:
        conn.close()
    return get_shot(shot_id)


def add_shot(sb_id: str, after_shot_id: Optional[str] = None, **fields) -> Dict[str, Any]:
    board = get_storyboard(sb_id)
    positions = [s["position"] for s in board["shots"]]
    if after_shot_id:
        after = next((s for s in board["shots"] if s["id"] == after_shot_id), None)
        insert_at = (after["position"] + 1) if after else (max(positions, default=0) + 1)
    else:
        insert_at = max(positions, default=0) + 1
    now = _now()
    conn = get_connection()
    try:
        conn.execute("UPDATE storyboard_shots SET position = position + 1 WHERE storyboard_id = ? AND position >= ?", (sb_id, insert_at))
        shot_id = f"shot_{uuid.uuid4().hex[:10]}"
        conn.execute(
            """INSERT INTO storyboard_shots
               (id, storyboard_id, position, label, heading, action, speaker, dialogue, framing, duration_s,
                engine, camera_motion, keyframe_source, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                shot_id, sb_id, insert_at, fields.get("label") or f"shot_{insert_at:02d}", fields.get("heading", ""),
                fields.get("action", "New shot"), fields.get("speaker", ""), fields.get("dialogue", ""),
                fields.get("framing", "medium"), float(fields.get("duration_s", 4.0)), fields.get("engine", "auto"),
                fields.get("camera_motion", "push_in"), fields.get("keyframe_source", "flux"), "PLANNED", now, now,
            ),
        )
        conn.execute("UPDATE storyboards SET updated_at = ? WHERE id = ?", (now, sb_id))
        conn.commit()
    finally:
        conn.close()
    return get_shot(shot_id)


def delete_shot(shot_id: str) -> None:
    shot = get_shot(shot_id)
    conn = get_connection()
    try:
        conn.execute("DELETE FROM storyboard_shots WHERE id = ?", (shot_id,))
        conn.execute(
            "UPDATE storyboard_shots SET position = position - 1 WHERE storyboard_id = ? AND position > ?",
            (shot["storyboard_id"], shot["position"]),
        )
        conn.execute("UPDATE storyboards SET updated_at = ? WHERE id = ?", (_now(), shot["storyboard_id"]))
        conn.commit()
    finally:
        conn.close()


def reorder_shots(sb_id: str, ordered_ids: List[str]) -> Dict[str, Any]:
    board = get_storyboard(sb_id)
    existing = {s["id"] for s in board["shots"]}
    if set(ordered_ids) != existing:
        raise StoryboardError("Reorder list must contain exactly the storyboard's shots")
    conn = get_connection()
    try:
        for position, shot_id in enumerate(ordered_ids, start=1):
            conn.execute("UPDATE storyboard_shots SET position = ? WHERE id = ?", (position, shot_id))
        conn.execute("UPDATE storyboards SET updated_at = ? WHERE id = ?", (_now(), sb_id))
        conn.commit()
    finally:
        conn.close()
    return get_storyboard(sb_id)


def delete_storyboard(sb_id: str) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM storyboards WHERE id = ?", (sb_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------

def add_candidate(
    shot_id: str, kind: str, file_path: str, *, engine: str = "", seed: Optional[int] = None,
    prompt: str = "", duration_s: Optional[float] = None, scores: Optional[Dict[str, Any]] = None,
    provenance: Optional[Dict[str, Any]] = None, asset_id: Optional[str] = None, job_id: Optional[str] = None,
    select: bool = False,
) -> Dict[str, Any]:
    cand_id = f"cand_{uuid.uuid4().hex[:10]}"
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO shot_candidates (id, shot_id, kind, file_path, engine, seed, prompt, duration_s, scores_json,
               provenance_json, asset_id, job_id, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cand_id, shot_id, kind, str(file_path), engine, seed, prompt, duration_s, json.dumps(scores or {}),
             json.dumps(provenance or {}), asset_id, job_id, _now()),
        )
        if select:
            column = {"keyframe": "selected_keyframe_id", "clip": "selected_clip_id", "speech": "selected_speech_id"}[kind]
            conn.execute(f"UPDATE storyboard_shots SET {column} = ?, updated_at = ? WHERE id = ?", (cand_id, _now(), shot_id))
        conn.commit()
        return _row(conn.execute("SELECT * FROM shot_candidates WHERE id = ?", (cand_id,)).fetchone())
    finally:
        conn.close()


def get_candidate(cand_id: str) -> Dict[str, Any]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM shot_candidates WHERE id = ?", (cand_id,)).fetchone()
        if not row:
            raise StoryboardError(f"Candidate not found: {cand_id}")
        item = _row(row)
        item["scores"] = _json(item.pop("scores_json"))
        item["provenance"] = _json(item.pop("provenance_json"))
        return item
    finally:
        conn.close()


def select_candidate(cand_id: str) -> Dict[str, Any]:
    cand = get_candidate(cand_id)
    column = {"keyframe": "selected_keyframe_id", "clip": "selected_clip_id", "speech": "selected_speech_id"}[cand["kind"]]
    patch = {column: cand_id}
    return update_shot(cand["shot_id"], patch)


def candidate_from_asset(shot_id: str, asset_id: str) -> Dict[str, Any]:
    """Promote any registered image asset (upload, generated, Qwen edit) to a keyframe candidate."""
    asset = AssetFactory().get_asset(asset_id)
    if not asset or not Path(asset.file_path).exists():
        raise StoryboardError(f"Asset not found on disk: {asset_id}")
    shot = get_shot(shot_id)
    board = get_storyboard(shot["storyboard_id"])
    width, height = ASPECTS[board["settings"]["aspect_ratio"]]
    target = _shot_dir(board, shot_id) / f"keyframe_{uuid.uuid4().hex[:8]}.jpg"
    img = Image.open(asset.file_path).convert("RGB")
    ImageOps.fit(img, (width, height), method=Image.Resampling.LANCZOS).save(target, "JPEG", quality=95)
    return add_candidate(
        shot_id, "keyframe", str(target), engine="asset", prompt=asset.name,
        provenance={"source_asset_id": asset_id, "kind": asset.kind}, asset_id=asset_id, select=True,
    )


# ---------------------------------------------------------------------------
# Engine resolution
# ---------------------------------------------------------------------------

def available_engines() -> Dict[str, Dict[str, Any]]:
    from app.core.wangp_engines import engine_status

    caps = discover_capabilities()
    by_id = {e["id"]: e for e in caps["engines"]}
    wangp = engine_status()
    return {
        "2.5d": {"label": "2.5D camera move", "available": True, "note": "Deterministic FFmpeg motion over the keyframe."},
        "ltx": {"label": "LTX-Video 0.9.5", "available": by_id["ltx_video_095"]["selectable"], "note": by_id["ltx_video_095"]["note"]},
        "h3": {"label": "MiniMax H3 (WanGP)", "available": wangp["h3"]["available"], "note": wangp["h3"]["note"]},
        "scail": {"label": "SCAIL-2 performance", "available": False, "note": "Controlled-performance route needs a driving video; not exposed per shot yet."},
    }


def voice_engines() -> Dict[str, Dict[str, Any]]:
    from app.core.wangp_engines import engine_status
    wangp = engine_status()
    return {
        "windows_sapi": {"label": "Windows offline voices", "available": True, "note": "Instant, robotic."},
        "chatterbox": {"label": "Chatterbox Multilingual (WanGP)", "available": wangp["chatterbox"]["available"], "note": wangp["chatterbox"]["note"]},
    }


def music_engines() -> Dict[str, Dict[str, Any]]:
    from app.core.wangp_engines import engine_status
    wangp = engine_status()
    return {
        "off": {"label": "Off", "available": True, "note": ""},
        "procedural": {"label": "Procedural ambient bed", "available": True, "note": "Synth chords, not a music model."},
        "ace_step": {"label": "ACE-Step 1.5 (WanGP)", "available": wangp["ace_step"]["available"], "note": wangp["ace_step"]["note"]},
    }


def resolve_engine(shot: Dict[str, Any], engines: Dict[str, Dict[str, Any]]) -> str:
    requested = shot.get("engine") or "auto"
    if requested != "auto":
        if not engines.get(requested, {}).get("available"):
            raise StoryboardError(f"Engine '{requested}' is not available on this machine: {engines.get(requested, {}).get('note', '')}")
        return requested
    risky = any(word in (shot.get("action") or "").lower() for word in (
        "hand", "phone", "display", "screen", "grip", "hold", "face", "walk", "run", "fight", "dance",
    ))
    if (shot.get("dialogue") or risky) or not engines["ltx"]["available"]:
        return "2.5d"
    return "ltx"


# ---------------------------------------------------------------------------
# Job enqueue helpers
# ---------------------------------------------------------------------------

def enqueue(kind: JobKind, board: Dict[str, Any], payload: Dict[str, Any], shot_id: Optional[str] = None, priority: int = 50):
    payload = {"storyboard_id": board["id"], **payload}
    return DurableQueue.enqueue(JobCreate(
        project_id=board["project_id"], kind=kind, shot_id=shot_id, priority=priority, payload_json=payload, max_attempts=1,
    ))


# ---------------------------------------------------------------------------
# Job handlers (called by the worker inside the GPU lease)
# ---------------------------------------------------------------------------

def _speech_duration(path: str) -> float:
    with wave.open(path, "rb") as wav:
        return wav.getnframes() / wav.getframerate()


def _selected(shot: Dict[str, Any], kind: str) -> Optional[Dict[str, Any]]:
    column = {"keyframe": "selected_keyframe_id", "clip": "selected_clip_id", "speech": "selected_speech_id"}[kind]
    cand_id = shot.get(column)
    if not cand_id:
        return None
    try:
        cand = get_candidate(cand_id)
    except StoryboardError:
        return None
    return cand if Path(cand["file_path"]).exists() else None


def _previous_keyframe(board: Dict[str, Any], shot: Dict[str, Any]) -> Optional[str]:
    for prev in reversed([s for s in board["shots"] if s["position"] < shot["position"]]):
        cand = _selected(prev, "keyframe")
        if cand:
            return cand["file_path"]
    return None


def handle_keyframes(job_id: str, payload: Dict[str, Any]) -> List[str]:
    from app.core.scene_artist import build_ai_prompt, render_cinematic_keyframe
    from app.core.visual_qa.dino_extractor import DINOExtractor

    board = get_storyboard(payload["storyboard_id"])
    shot = get_shot(payload["shot_id"])
    settings = board["settings"]
    width, height = ASPECTS[settings["aspect_ratio"]]
    count = max(1, min(4, int(payload.get("count") or settings.get("keyframe_candidates") or 2)))
    source = payload.get("keyframe_source") or shot.get("keyframe_source") or "flux"
    out_dir = _shot_dir(board, shot["id"])
    produced: List[str] = []

    progress_emit(job_id, "keyframe", f"{shot['label']}: preparing keyframe ({source}).", 5)

    if source == "reference":
        ref_id = payload.get("reference_asset_id") or shot.get("reference_asset_id")
        if not ref_id:
            raise StoryboardError("Shot has no reference asset; pick one from the library first.")
        cand = candidate_from_asset(shot["id"], ref_id)
        progress_emit(job_id, "keyframe", f"{shot['label']}: reference image fitted as keyframe.", 100)
        return [cand["id"]]

    if source == "inherit":
        previous = _previous_keyframe(board, shot)
        if not previous:
            raise StoryboardError("No earlier shot has a selected keyframe to inherit from.")
        target = out_dir / f"keyframe_{uuid.uuid4().hex[:8]}.jpg"
        shutil.copy2(previous, target)
        cand = add_candidate(shot["id"], "keyframe", str(target), engine="inherit", provenance={"inherited_from": previous}, job_id=job_id, select=True)
        progress_emit(job_id, "keyframe", f"{shot['label']}: inherited the previous shot's keyframe.", 100)
        return [cand["id"]]

    base_seed = int(shot.get("seed") if shot.get("seed") is not None else settings["seed"]) + shot["position"] * 101
    prompt = build_ai_prompt(board["title"], shot["heading"], shot["action"], shot["speaker"], shot["dialogue"],
                             settings["genre"], framing=shot["framing"])
    if settings.get("style_prompt"):
        prompt = f"{prompt}. {settings['style_prompt'].strip()}"
    for index in range(count):
        seed = base_seed + index
        progress_emit(job_id, "keyframe", f"{shot['label']}: FLUX candidate {index + 1}/{count} (seed {seed}).", 10 + int(80 * index / count))
        target = out_dir / f"keyframe_{seed}_{uuid.uuid4().hex[:6]}.jpg"
        render_cinematic_keyframe(
            title=board["title"], scene_heading=shot["heading"], speaker=shot["speaker"], dialogue=shot["dialogue"],
            genre=settings["genre"], beat_number=shot["position"], output_image_path=str(target), action=shot["action"],
            framing=shot["framing"], width=width, height=height, seed=seed, progress_client_id=job_id,
        )
        asset = AssetFactory().create_asset(
            project_id=board["project_id"], asset_id=f"KF_{board['id']}_{shot['id']}_{seed}", kind=AssetKind.KEYFRAME.value,
            name=f"{shot['label']} keyframe s{seed}", file_path=str(target),
            provenance={"prompt": prompt, "seed": seed, "engine": "flux2_klein"},
        )
        cand = add_candidate(shot["id"], "keyframe", str(target), engine="flux2_klein", seed=seed, prompt=prompt,
                             provenance={"width": width, "height": height}, asset_id=asset.id, job_id=job_id)
        produced.append(cand["id"])

    # Score against the storyboard's identity anchor (previous keyframe) when one exists.
    anchor = _previous_keyframe(board, shot)
    if anchor and produced:
        progress_emit(job_id, "keyframe", f"{shot['label']}: scoring candidates with DINO against the previous keyframe.", 92)
        try:
            extractor = DINOExtractor()
            paths = [get_candidate(c)["file_path"] for c in produced]
            evaluations = extractor.evaluate_candidates(paths, ref_char_path=anchor)
            conn = get_connection()
            try:
                for cand_id, evaluation in zip(produced, evaluations):
                    scores = {
                        "identity_similarity": evaluation["raw_scores"]["whole_subject_similarity"],
                        "composite": evaluation["normalized_scores"]["composite"],
                    }
                    conn.execute("UPDATE shot_candidates SET scores_json = ? WHERE id = ?", (json.dumps(scores), cand_id))
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:  # scoring is advisory
            progress_emit(job_id, "keyframe", f"DINO scoring skipped: {exc}", level="warning")

    refreshed = get_shot(shot["id"])
    if not refreshed.get("selected_keyframe_id") and produced:
        best = max(produced, key=lambda c: (get_candidate(c)["scores"].get("composite") or 0))
        select_candidate(best)
    progress_emit(job_id, "keyframe", f"{shot['label']}: {len(produced)} keyframe candidate(s) ready.", 100)
    return produced


def handle_clip(job_id: str, payload: Dict[str, Any]) -> List[str]:
    from app.core.scene_artist import render_shot_video_clip

    board = get_storyboard(payload["storyboard_id"])
    shot = get_shot(payload["shot_id"])
    settings = board["settings"]
    width, height = ASPECTS[settings["aspect_ratio"]]
    keyframe = _selected(shot, "keyframe")
    if not keyframe:
        raise StoryboardError("Select a keyframe before rendering motion for this shot.")
    engines = available_engines()
    engine = payload.get("engine") or resolve_engine(shot, engines)
    if engine not in engines or not engines[engine]["available"]:
        raise StoryboardError(f"Engine '{engine}' is not available: {engines.get(engine, {}).get('note', '')}")
    duration = float(shot["duration_s"])
    speech = _selected(shot, "speech")
    if speech and speech.get("duration_s"):
        duration = max(duration, float(speech["duration_s"]) + 0.6)
    seed = int(shot.get("seed") if shot.get("seed") is not None else settings["seed"]) + shot["position"] * 7
    out = _shot_dir(board, shot["id"]) / f"clip_{engine}_{uuid.uuid4().hex[:8]}.mp4"
    progress_emit(job_id, "motion", f"{shot['label']}: rendering {duration:.1f}s with {engine}.", 5)

    if engine == "ltx":
        from app.core.local_video import render_ltx_video
        ok = render_ltx_video(
            keyframe["file_path"], str(out), shot["action"], duration, settings["aspect_ratio"], seed,
            quality_profile=settings["quality_profile"], client_id=job_id,
            progress_callback=lambda message, pct: progress_emit(
                job_id, "motion", f"{shot['label']}: {message}", int(5 + 90 * min(1.0, max(0.0, (pct - 18) / 44)))
            ),
        )
    elif engine == "2.5d":
        ok = render_shot_video_clip(
            image_path=keyframe["file_path"], output_mp4_path=str(out), duration_s=duration, beat_number=shot["position"],
            framing=shot["framing"], width=width, height=height, genre=settings["genre"], motion=shot.get("camera_motion") or "push_in",
        )
    elif engine == "h3":
        from app.core.wangp_engines import render_h3_i2v
        h3_prompt = shot["action"]
        if shot.get("dialogue"):
            h3_prompt += f' The character says clearly (S1) <d>[English] {shot["dialogue"]}</d> with precise lip synchronization.'
        ok = render_h3_i2v(
            keyframe["file_path"], str(out), h3_prompt, duration, settings["aspect_ratio"], seed,
            progress=lambda m, p: progress_emit(job_id, "motion", f"{shot['label']}: {m}", int(5 + 0.9 * p)),
        )
    else:
        raise StoryboardError(f"Engine '{engine}' has no storyboard adapter yet.")
    if not ok or not out.exists() or out.stat().st_size < 1000:
        raise StoryboardError(f"{engine} produced no valid clip for {shot['label']}.")
    cand = add_candidate(shot["id"], "clip", str(out), engine=engine, seed=seed, prompt=shot["action"], duration_s=duration,
                         provenance={"camera_motion": shot.get("camera_motion"), "keyframe_candidate": keyframe["id"],
                                     "quality_profile": settings["quality_profile"]}, job_id=job_id, select=True)
    if duration != float(shot["duration_s"]):
        update_shot(shot["id"], {"duration_s": round(duration, 2), "selected_clip_id": cand["id"]})
    progress_emit(job_id, "motion", f"{shot['label']}: clip ready ({engine}).", 100)
    return [cand["id"]]


def handle_speech(job_id: str, payload: Dict[str, Any]) -> List[str]:
    from app.core.audio.speech_synth import synthesize_speech

    board = get_storyboard(payload["storyboard_id"])
    targets = [s for s in board["shots"] if s["dialogue"] and (not payload.get("shot_id") or s["id"] == payload["shot_id"])]
    if not targets:
        return []
    voice_indices = {name: i for i, name in enumerate(sorted({s["speaker"] for s in board["shots"] if s["dialogue"]}))}
    engine = payload.get("voice_engine") or board["settings"].get("voice_engine") or "windows_sapi"
    produced = []
    for index, shot in enumerate(targets, start=1):
        progress_emit(job_id, "speech", f"{shot['label']}: synthesizing dialogue with {engine} ({index}/{len(targets)}).", int(100 * (index - 1) / len(targets)))
        out = _shot_dir(board, shot["id"]) / f"speech_{uuid.uuid4().hex[:8]}.wav"
        if engine == "chatterbox":
            from app.core.wangp_engines import synthesize_chatterbox
            ok = synthesize_chatterbox(
                shot["dialogue"], str(out), language=board["settings"].get("voice_language", "en"),
                seed=1000 + voice_indices.get(shot["speaker"], 0) * 97,
                progress=lambda m, p: progress_emit(job_id, "speech", f"{shot['label']}: {m}"),
            )
        else:
            ok = synthesize_speech(shot["dialogue"], str(out), voice_index=voice_indices.get(shot["speaker"], 0))
        if not ok:
            raise StoryboardError(f"Speech synthesis failed for {shot['label']}.")
        duration = _speech_duration(str(out))
        cand = add_candidate(shot["id"], "speech", str(out), engine=engine, prompt=shot["dialogue"],
                             duration_s=round(duration, 2), provenance={"speaker": shot["speaker"]}, job_id=job_id, select=True)
        if duration + 0.6 > float(shot["duration_s"]):
            update_shot(shot["id"], {"duration_s": round(duration + 0.6, 2), "selected_speech_id": cand["id"]})
        produced.append(cand["id"])
    progress_emit(job_id, "speech", f"Dialogue ready for {len(produced)} shot(s).", 100)
    return produced


def handle_assemble(job_id: str, payload: Dict[str, Any]) -> List[str]:
    import hashlib
    from app.core.audio.foley_engine import FoleyBackend, FoleyCategory, FoleyCue, FoleyEngine, FoleyRequest
    from app.core.audio.speech_synth import assemble_speech_timeline, synthesize_music_bed
    from app.core.frame_interpolation import interpolate_video_2x
    from app.core.post.assembly_engine import AssemblyEngine, AssemblyRequest, ShotClipInput, SubtitleEntry
    from app.core.post.ffmpeg_utils import run_ffmpeg
    from app.core.thumbnails.thumbnail_manager import ThumbnailGenerationRequest, ThumbnailManager

    board = get_storyboard(payload["storyboard_id"])
    settings = {**board["settings"], **(payload.get("settings") or {})}
    width, height = ASPECTS[settings["aspect_ratio"]]
    shots = board["shots"]
    missing = [s["label"] for s in shots if not _selected(s, "clip")]
    if missing:
        raise StoryboardError(f"These shots have no rendered clip yet: {', '.join(missing)}")

    render_id = f"render_{uuid.uuid4().hex[:10]}"
    out_dir = _storyboard_dir(board) / "renders" / render_id
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_dir = out_dir / "audio"
    audio_dir.mkdir(exist_ok=True)

    progress_emit(job_id, "assembly", "Collecting selected clips and dialogue.", 5)
    shot_clips, subtitles, timeline, cursor = [], [], [], 0.0
    for shot in shots:
        clip = _selected(shot, "clip")
        speech = _selected(shot, "speech")
        duration = float(clip.get("duration_s") or shot["duration_s"])
        shot_clips.append(ShotClipInput(shot_id=shot["label"], video_path=clip["file_path"], in_trim_s=0.0, out_trim_s=duration))
        timeline.append({"shot_id": shot["label"], "duration_s": duration, "action": shot["action"],
                         "speech_path": speech["file_path"] if speech else None})
        if speech and shot["dialogue"]:
            subtitles.append(SubtitleEntry(
                start_s=round(cursor + 0.3, 2), end_s=round(cursor + 0.3 + float(speech.get("duration_s") or duration - 0.6), 2),
                text=shot["dialogue"], character_name=(shot["speaker"] or "").capitalize(),
            ))
        cursor += duration
    total = cursor

    dialogue_wav = str(audio_dir / "dialogue_master.wav")
    speech_ok = any(t["speech_path"] for t in timeline) and assemble_speech_timeline(timeline, dialogue_wav, total)

    foley_wav, foley_ok, foley_backend = None, False, "off"
    if settings.get("foley_engine") == "library":
        progress_emit(job_id, "audio", "Placing action-matched Foley cues.", 25)
        cues, at = [], 0.0
        for t in timeline:
            action = t["action"].lower()
            if any(w in action for w in ("walk", "step", "run", "dash", "chase")):
                cues.append(FoleyCue(action_type=FoleyCategory.FOOTSTEPS, cue_id="SFX_FOOTSTEPS_CONCRETE_V001", start_time_s=at + 0.2,
                                     duration_s=min(2.5, t["duration_s"]), gain_db=-5.0, description="Footsteps"))
            if "door" in action:
                cues.append(FoleyCue(action_type=FoleyCategory.DOORS, cue_id="SFX_DOOR_OPEN_CREAK_V001", start_time_s=at + 0.2,
                                     duration_s=1.5, gain_db=-4.0, description="Door"))
            if any(w in action for w in ("hit", "punch", "fall", "slam", "impact", "fight")):
                cues.append(FoleyCue(action_type=FoleyCategory.IMPACT, cue_id="SFX_IMPACT_TABLE_THUMP_V001", start_time_s=at + min(0.7, t["duration_s"] / 2),
                                     duration_s=1.0, gain_db=-3.0, description="Impact"))
            at += t["duration_s"]
        cues.insert(0, FoleyCue(action_type=FoleyCategory.AMBIENCE, cue_id="SFX_AMBIENCE_ROOM_TONE_V001", start_time_s=0.0,
                                duration_s=total, gain_db=-15.0, description="Ambience"))
        result = FoleyEngine.generate_foley(FoleyRequest(project_id=board["project_id"], shot_id=render_id, duration_s=total,
                                                         backend=FoleyBackend.LIBRARY_FALLBACK, cues=cues, output_dir=str(audio_dir)), mock_mode=False)
        foley_wav = result.audio_path
        foley_ok = bool(foley_wav and Path(foley_wav).exists())
        foley_backend = result.backend_used

    music_wav, music_ok = str(audio_dir / "music_bed.wav"), False
    if settings.get("music_engine") == "procedural":
        music_ok = synthesize_music_bed(settings["genre"], total, music_wav)
    elif settings.get("music_engine") == "ace_step":
        from app.core.wangp_engines import generate_ace_step_music
        progress_emit(job_id, "audio", "Generating the music bed with ACE-Step.", 30)
        description = settings.get("music_prompt") or f"{settings['genre'].replace('_', ' ')} cinematic underscore, instrumental, atmospheric"
        music_ok = generate_ace_step_music(description, total + 2, music_wav, seed=int(settings.get("seed", 42)),
                                           progress=lambda m, p: progress_emit(job_id, "audio", f"ACE-Step: {m}"))

    progress_emit(job_id, "assembly", f"Encoding the {width}x{height} master with subtitles.", 45)
    assembly = AssemblyEngine.assemble(AssemblyRequest(
        project_id=board["project_id"], sequence_id=render_id, shots=shot_clips,
        dialogue_audio_path=dialogue_wav if speech_ok else None, foley_audio_path=foley_wav if foley_ok else None,
        music_audio_path=music_wav if music_ok else None, music_ducking_db=-12.0, subtitles=subtitles,
        burn_subtitles=bool(settings.get("burn_subtitles", True)), target_width=width, target_height=height, output_dir=str(out_dir),
    ), mock_mode=False)
    master = assembly.master_video_path
    if settings.get("frame_interpolation") == "film_2x":
        progress_emit(job_id, "frame_interpolation", "FILM 2x interpolation on the master.", 70)
        target = str(Path(master).with_name(Path(master).stem + "_film2x.mp4"))
        interpolate_video_2x(master, target, client_id=job_id)
        master = target

    progress_emit(job_id, "thumbnails", "Creating thumbnail variants.", 80)
    hero = next((_selected(s, "keyframe")["file_path"] for s in reversed(shots) if _selected(s, "keyframe")), None)
    thumbs = ThumbnailManager.generate_thumbnails(ThumbnailGenerationRequest(
        project_id=board["project_id"], episode_id=render_id, series_title=board["title"], episode_number=1,
        episode_title=board["title"], synopsis=board["script_text"][:150], character_ref_path=hero, output_dir=str(out_dir / "thumbnails"),
    ), mock_mode=False)
    thumb_paths = [str(p) for p in Path(out_dir / "thumbnails").glob("*.jpg")] if (out_dir / "thumbnails").exists() else []

    qa: Dict[str, Any] = {"visual_dino_score": None, "visual_dino_shots": [], "warnings": []}
    if settings.get("qa_mode") == "dino":
        progress_emit(job_id, "quality_check", "Measuring DINO consistency per shot.", 90)
        from app.core.visual_qa.dino_extractor import DINOExtractor
        extractor = DINOExtractor()
        for shot, clip in zip(shots, shot_clips):
            reference = _selected(shot, "keyframe")
            if not reference:
                continue
            sample = out_dir / f"{shot['label']}_qa_frame.jpg"
            code, _, error = run_ffmpeg(["-y", "-ss", str(max(0.1, clip.out_trim_s / 2)), "-i", clip.video_path, "-frames:v", "1", str(sample)])
            if code:
                qa["warnings"].append(f"QA frame extraction failed for {shot['label']}")
                continue
            evaluation = extractor.evaluate_candidates([str(sample)], ref_char_path=reference["file_path"])[0]
            qa["visual_dino_shots"].append({"shot_id": shot["label"], "identity_similarity": evaluation["raw_scores"]["whole_subject_similarity"],
                                            "composite_score": evaluation["normalized_scores"]["composite"], "frame_path": str(sample)})
        if qa["visual_dino_shots"]:
            qa["visual_dino_score"] = round(sum(i["identity_similarity"] for i in qa["visual_dino_shots"]) / len(qa["visual_dino_shots"]), 4)
    qa.update({"overall_decision": "REVIEW_REQUIRED", "speech_backend": settings["voice_engine"], "foley_backend": foley_backend,
               "music_backend": settings.get("music_engine"), "frame_interpolation": settings.get("frame_interpolation"),
               "engines_used": sorted({_selected(s, "clip")["engine"] for s in shots})})

    with open(master, "rb") as handle:
        sha = hashlib.file_digest(handle, "sha256").hexdigest()
    provenance = {"version": "2.0.0", "master_sha256": sha, "storyboard_id": board["id"], "shots": [
        {"label": s["label"], "keyframe": _selected(s, "keyframe")["id"], "clip": _selected(s, "clip")["id"],
         "engine": _selected(s, "clip")["engine"], "seed": _selected(s, "clip")["seed"]} for s in shots
    ], "assembly": assembly.provenance_json}
    srt = assembly.subtitles_path
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO storyboard_renders (id, storyboard_id, master_video_path, srt_path, thumbnails_json, qa_json, provenance_json,
               settings_json, duration_s, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (render_id, board["id"], master, srt, json.dumps(thumb_paths), json.dumps(qa), json.dumps(provenance),
             json.dumps(settings), round(total, 2), _now()),
        )
        conn.execute("UPDATE storyboards SET status = 'RENDERED', updated_at = ? WHERE id = ?", (_now(), board["id"]))
        conn.commit()
    finally:
        conn.close()
    progress_emit(job_id, "completed", f"Master ready: {Path(master).name}", 100)
    return [render_id]


HANDLERS = {
    JobKind.KEYFRAME_GEN: handle_keyframes,
    JobKind.RENDER_SHOT: handle_clip,
    JobKind.AUDIO_GEN: handle_speech,
    JobKind.PACKAGE: handle_assemble,
}
