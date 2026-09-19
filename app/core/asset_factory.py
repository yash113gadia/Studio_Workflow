import json
import os
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.core.config import settings
from app.core.database import get_connection
from app.core.models import AssetRecord, AssetKind, JobKind, JobCreate
from app.core.queue import DurableQueue


class AssetFactory:
    """
    Character Asset Factory v1
    Enforces Phase 4 requirements:
    1. 3 casting candidates generated from Studio UI / API.
    2. One approved as CHAR_*_V001 (immutable Tier 0).
    3. At least 5 distinct canonical compositions produced from canonical reference.
    4. Full provenance recorded for every image in SQLite.
    5. Immutable canonical references cannot be modified in place.
    """

    CANONICAL_ANGLE_SPECS = [
        {
            "suffix": "FRONT_NEUTRAL",
            "name": "Front Neutral",
            "prompt": "canonical character portrait, front view facing camera, neutral calm expression, clean solid studio background, 8k"
        },
        {
            "suffix": "THREE_QUARTER_LEFT",
            "name": "Three-Quarter Turn Left",
            "prompt": "canonical character portrait, three-quarter turn facing left, subtle intense gaze, clean solid studio background, 8k"
        },
        {
            "suffix": "THREE_QUARTER_RIGHT",
            "name": "Three-Quarter Turn Right",
            "prompt": "canonical character portrait, three-quarter turn facing right, subtle determined expression, clean solid studio background, 8k"
        },
        {
            "suffix": "PROFILE_LEFT",
            "name": "Profile Left",
            "prompt": "canonical character portrait, sharp side profile facing left, rim light, clean solid studio background, 8k"
        },
        {
            "suffix": "PROFILE_RIGHT",
            "name": "Profile Right",
            "prompt": "canonical character portrait, sharp side profile facing right, rim light, clean solid studio background, 8k"
        }
    ]

    def __init__(self, conn: Optional[sqlite3.Connection] = None):
        self._conn = conn

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn:
            return self._conn
        return get_connection()

    def create_asset(
        self,
        project_id: str,
        asset_id: str,
        kind: str,
        name: str,
        file_path: str,
        version: str = "v001",
        tier: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
        provenance: Optional[Dict[str, Any]] = None
    ) -> AssetRecord:
        conn = self._get_conn()
        now = datetime.utcnow().isoformat()
        metadata_json = json.dumps(metadata or {})
        provenance_json = json.dumps(provenance or {})

        # Immutability check: if asset exists and is Tier 0 canonical, reject modification
        cursor = conn.execute("SELECT id, tier, kind FROM assets WHERE id = ?", (asset_id,))
        existing = cursor.fetchone()
        if existing:
            if existing["tier"] == 0 and existing["kind"] == AssetKind.CANONICAL_REF.value:
                raise ValueError(f"Immutable Asset Violation: Canonical reference {asset_id} is immutable and cannot be overwritten.")
            cursor.execute("""
            UPDATE assets SET 
                project_id = ?, tier = ?, kind = ?, version = ?, name = ?, 
                file_path = ?, metadata_json = ?, provenance_json = ?, created_at = ?
            WHERE id = ?
            """, (project_id, tier, kind, version, name, file_path, metadata_json, provenance_json, now, asset_id))
        else:
            cursor.execute("""
            INSERT INTO assets (id, project_id, tier, kind, version, name, file_path, metadata_json, provenance_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (asset_id, project_id, tier, kind, version, name, file_path, metadata_json, provenance_json, now))

        conn.commit()
        return AssetRecord(
            id=asset_id,
            project_id=project_id,
            tier=tier,
            kind=kind,
            version=version,
            name=name,
            file_path=file_path,
            metadata_json=metadata or {},
            provenance_json=provenance or {},
            created_at=now
        )

    def get_asset(self, asset_id: str) -> Optional[AssetRecord]:
        conn = self._get_conn()
        cursor = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return AssetRecord(
            id=row["id"],
            project_id=row["project_id"],
            tier=row["tier"],
            kind=row["kind"],
            version=row["version"],
            name=row["name"],
            file_path=row["file_path"],
            metadata_json=json.loads(row["metadata_json"]),
            provenance_json=json.loads(row["provenance_json"]),
            created_at=row["created_at"]
        )

    def list_assets(self, project_id: str, kind: Optional[str] = None) -> List[AssetRecord]:
        conn = self._get_conn()
        if kind:
            cursor = conn.execute("SELECT * FROM assets WHERE project_id = ? AND kind = ? ORDER BY created_at DESC", (project_id, kind))
        else:
            cursor = conn.execute("SELECT * FROM assets WHERE project_id = ? ORDER BY created_at DESC", (project_id,))
        rows = cursor.fetchall()
        return [
            AssetRecord(
                id=row["id"],
                project_id=row["project_id"],
                tier=row["tier"],
                kind=row["kind"],
                version=row["version"],
                name=row["name"],
                file_path=row["file_path"],
                metadata_json=json.loads(row["metadata_json"]),
                provenance_json=json.loads(row["provenance_json"]),
                created_at=row["created_at"]
            )
            for row in rows
        ]

    def create_casting_jobs(
        self,
        project_id: str,
        character_name: str,
        prompt_description: str,
        count: int = 3,
        seed_base: int = 1000
    ) -> List[Dict[str, Any]]:
        style_prefix = "STYLE_SERIES_A_V001: Stylized cinematic 3D illustration, graphic novel aesthetic, sharp lighting, studio portrait:"
        jobs = []

        for i in range(count):
            seed = seed_base + (i * 137)
            candidate_id = f"CAND_{character_name.upper()}_{i+1:03d}"
            full_prompt = f"{style_prefix} {character_name}, {prompt_description}, neutral clean studio background, highly detailed, photorealistic 3d rendering, 8k"
            
            payload = {
                "workflow_template": "flux_casting_v001",
                "character_name": character_name,
                "candidate_index": i + 1,
                "candidate_id": candidate_id,
                "prompt": full_prompt,
                "negative_prompt": "distorted face, blurry, multiple heads, deformed hands, text, watermark",
                "seed": seed,
                "width": 480,
                "height": 864,
                "steps": 20,
                "cfg": 4.0,
                "filename_prefix": f"casting_{character_name.lower()}_{i+1:03d}"
            }

            job = DurableQueue.enqueue(JobCreate(
                project_id=project_id,
                kind=JobKind.CANONICAL_CASTING,
                priority=40,
                backend="comfyui",
                payload_json=payload
            ))

            jobs.append({
                "job_id": job.id,
                "candidate_id": candidate_id,
                "candidate_index": i + 1,
                "seed": seed,
                "prompt": full_prompt
            })

        return jobs

    def register_candidate_asset(
        self,
        project_id: str,
        candidate_id: str,
        character_name: str,
        image_path: str,
        prompt: str,
        seed: int,
        workflow_name: str = "flux_casting_v001",
        model_hashes: Optional[Dict[str, str]] = None
    ) -> AssetRecord:
        provenance = {
            "genesis_workflow": workflow_name,
            "seed": seed,
            "prompt": prompt,
            "character_name": character_name,
            "models": model_hashes or {
                "vae": "868fe7b343cc8f3a19dbcfcafbc3d5f888802be3f89bd81b65b3621a066ce8f3",
                "diffusion": "97ed34fe0567e436200f2faee3939b88f2b5d99f8af2a4dc16532c4245c0ccb6",
                "text_encoder": "6c671498573ac2f7a5501502ccce8d2b08ea6ca2f661c458e708f36b36edfc5a"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        return self.create_asset(
            project_id=project_id,
            asset_id=candidate_id,
            kind=AssetKind.CASTING_CANDIDATE.value,
            name=f"Casting Candidate {candidate_id}",
            file_path=image_path,
            version="v001",
            tier=1,
            metadata={"character_name": character_name, "seed": seed},
            provenance=provenance
        )

    def approve_character_casting(
        self,
        project_id: str,
        candidate_asset_id: str,
        character_code: str,
        approval_actor: str = "studio_admin"
    ) -> AssetRecord:
        candidate = self.get_asset(candidate_asset_id)
        if not candidate:
            raise ValueError(f"Candidate asset '{candidate_asset_id}' not found in project '{project_id}'")

        canonical_id = f"CHAR_{character_code.upper()}_V001"
        
        # Verify immutability: Cannot approve over an already locked canonical reference
        existing_canonical = self.get_asset(canonical_id)
        if existing_canonical:
            raise ValueError(f"Immutable Asset Violation: {canonical_id} already exists and is locked as Tier 0 immutable canon.")

        # Target storage path: projects/{project_id}/assets/characters/{canonical_id}/canonical_ref.png
        proj_dir = settings.paths.absolute(f"projects/{project_id}/assets/characters/{canonical_id}")
        proj_dir.mkdir(parents=True, exist_ok=True)
        dest_img = proj_dir / "canonical_ref.png"

        # Copy candidate image to immutable canonical reference location
        src_img = Path(candidate.file_path)
        if src_img.exists():
            shutil.copy2(src_img, dest_img)
        else:
            # Touch / create if simulated
            dest_img.touch(exist_ok=True)

        provenance = {
            "source_candidate_id": candidate_asset_id,
            "candidate_provenance": candidate.provenance_json,
            "approved_by": approval_actor,
            "approved_at": datetime.utcnow().isoformat(),
            "immutable_tier": 0,
            "canon_status": "APPROVED"
        }

        metadata = {
            "character_code": character_code.upper(),
            "character_name": candidate.metadata_json.get("character_name", character_code),
            "seed": candidate.metadata_json.get("seed"),
            "is_immutable": True
        }

        return self.create_asset(
            project_id=project_id,
            asset_id=canonical_id,
            kind=AssetKind.CANONICAL_REF.value,
            name=f"Canonical Reference {canonical_id}",
            file_path=str(dest_img),
            version="v001",
            tier=0,  # Tier 0 = Immutable Canonical Reference
            metadata=metadata,
            provenance=provenance
        )

    def create_canonical_angle_jobs(
        self,
        project_id: str,
        canonical_id: str,
        seed_base: int = 2000
    ) -> List[Dict[str, Any]]:
        canonical = self.get_asset(canonical_id)
        if not canonical:
            raise ValueError(f"Canonical asset '{canonical_id}' not found")

        jobs = []

        for i, spec in enumerate(self.CANONICAL_ANGLE_SPECS):
            seed = seed_base + (i * 271)
            angle_asset_id = f"{canonical_id}_{spec['suffix']}"
            payload = {
                "workflow_template": "flux_character_keyframe_v001",
                "canonical_asset_id": canonical_id,
                "canonical_image_path": canonical.file_path,
                "angle_asset_id": angle_asset_id,
                "angle_name": spec["name"],
                "prompt": spec["prompt"],
                "negative_prompt": "distorted, blurry, deformed hands, extra limbs, bad eyes, text",
                "seed": seed,
                "width": 480,
                "height": 864,
                "steps": 20,
                "cfg": 4.0,
                "filename_prefix": f"{canonical_id.lower()}_{spec['suffix'].lower()}"
            }

            job = DurableQueue.enqueue(JobCreate(
                project_id=project_id,
                kind=JobKind.KEYFRAME_GEN,
                priority=45,
                backend="comfyui",
                payload_json=payload
            ))


            jobs.append({
                "job_id": job.id,
                "angle_asset_id": angle_asset_id,
                "angle_name": spec["name"],
                "suffix": spec["suffix"],
                "seed": seed,
                "prompt": spec["prompt"]
            })

        return jobs

    def register_canonical_angle_asset(
        self,
        project_id: str,
        canonical_id: str,
        suffix: str,
        name: str,
        image_path: str,
        prompt: str,
        seed: int
    ) -> AssetRecord:
        canonical = self.get_asset(canonical_id)
        if not canonical:
            raise ValueError(f"Canonical reference {canonical_id} not found")

        angle_asset_id = f"{canonical_id}_{suffix}"
        provenance = {
            "parent_canonical_id": canonical_id,
            "parent_file_path": canonical.file_path,
            "derivation_workflow": "flux_character_keyframe_v001",
            "seed": seed,
            "prompt": prompt,
            "suffix": suffix,
            "derived_at": datetime.utcnow().isoformat()
        }

        return self.create_asset(
            project_id=project_id,
            asset_id=angle_asset_id,
            kind=AssetKind.CANONICAL_ANGLE.value,
            name=name,
            file_path=image_path,
            version="v001",
            tier=1,
            metadata={"parent_canonical": canonical_id, "suffix": suffix, "seed": seed},
            provenance=provenance
        )
