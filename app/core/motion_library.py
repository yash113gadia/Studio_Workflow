"""Driving Motion Library Manager — Preeti Studio SCAIL-2 Integration."""
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MotionRecord(BaseModel):
    motion_id: str
    name: str
    category: str
    duration_s: float
    framerate: int = 24
    loopable: bool = False
    driving_video_file: str
    driving_video_path: Optional[str] = None
    description: str = ""
    tags: List[str] = Field(default_factory=list)


class MotionLibrary:
    """Manages indexing, retrieval, and ingestion of driving performances for SCAIL-2."""

    def __init__(self, library_dir: Optional[str] = None):
        self.library_dir = Path(
            library_dir or os.path.join(os.getcwd(), "shared_assets", "motion_library")
        ).resolve()
        self.manifest_file = self.library_dir / "manifest.json"

    def get_manifest(self) -> Dict[str, Any]:
        if not self.manifest_file.exists():
            return {"version": "1.0.0", "motions": []}
        with open(self.manifest_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_motions(self, category: Optional[str] = None) -> List[MotionRecord]:
        manifest = self.get_manifest()
        motions = []
        for m in manifest.get("motions", []):
            if category and m.get("category") != category:
                continue
            video_path = str(self.library_dir / m.get("driving_video_file", ""))
            motions.append(
                MotionRecord(
                    motion_id=m["motion_id"],
                    name=m["name"],
                    category=m["category"],
                    duration_s=m["duration_s"],
                    framerate=m.get("framerate", 24),
                    loopable=m.get("loopable", False),
                    driving_video_file=m["driving_video_file"],
                    driving_video_path=video_path,
                    description=m.get("description", ""),
                    tags=m.get("tags", []),
                )
            )
        return motions

    def get_motion(self, motion_id: str) -> Optional[MotionRecord]:
        motions = self.list_motions()
        for m in motions:
            if m.motion_id == motion_id:
                return m
        return None

    def search_motions(self, query: str) -> List[MotionRecord]:
        q = query.lower().strip()
        results = []
        for m in self.list_motions():
            if (
                q in m.name.lower()
                or q in m.description.lower()
                or any(q in t.lower() for t in m.tags)
                or q in m.category.lower()
            ):
                results.append(m)
        return results

    def import_motion(
        self,
        name: str,
        category: str,
        video_src_path: str,
        duration_s: float,
        description: str = "",
        tags: Optional[List[str]] = None,
        loopable: bool = False,
    ) -> MotionRecord:
        """Imports a new human driving performance into the canonical motion library."""
        clean_name = "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")
        motion_id = f"MOTION_{clean_name.upper()}_V{uuid.uuid4().hex[:4].upper()}"
        filename = f"{clean_name}_{motion_id[-4:].lower()}.mp4"
        dest_path = self.library_dir / filename

        shutil.copy2(video_src_path, dest_path)

        new_entry = {
            "motion_id": motion_id,
            "name": name,
            "category": category,
            "duration_s": round(duration_s, 2),
            "framerate": 24,
            "loopable": loopable,
            "driving_video_file": filename,
            "description": description,
            "tags": tags or [],
        }

        manifest = self.get_manifest()
        manifest.setdefault("motions", []).append(new_entry)
        with open(self.manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return MotionRecord(
            motion_id=motion_id,
            name=name,
            category=category,
            duration_s=round(duration_s, 2),
            framerate=24,
            loopable=loopable,
            driving_video_file=filename,
            driving_video_path=str(dest_path),
            description=description,
            tags=tags or [],
        )
