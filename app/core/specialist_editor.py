"""Specialist Still Editor Engine — Qwen-Image-Edit-2511 INT8 Branch."""
import json
import os
import shutil
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from app.core.config import settings
from app.core.database import get_connection
from app.core.models import (
    AssetKind,
    AssetRecord,
    JobCreate,
    JobKind,
    SpecialistEditAction,
    SpecialistEditRequest,
    SpecialistEditResponse,
)
from app.core.queue import DurableQueue
from app.core.local_video import request as comfy_request
from app.core.visual_qa.dino_extractor import DINOExtractor
from app.core.render_guard import gpu_render_lease


ACTION_WORKFLOW_MAP = {
    SpecialistEditAction.PRESERVE_IDENTITY_CHANGE_OUTFIT: "qwen_edit_outfit_v001",
    SpecialistEditAction.REMOVE_UNWANTED_OBJECT: "qwen_edit_remove_object_v001",
    SpecialistEditAction.REPAIR_BACKGROUND: "qwen_edit_repair_bg_v001",
    SpecialistEditAction.DERIVE_ANGLE: "qwen_edit_derive_angle_v001",
    SpecialistEditAction.CORRECT_PROP: "qwen_edit_correct_prop_v001",
    SpecialistEditAction.MATERIAL_SWAP: "qwen_edit_material_swap_v001",
}

DEFAULT_INSTRUCTIONS = {
    SpecialistEditAction.PRESERVE_IDENTITY_CHANGE_OUTFIT: (
        "Change the character's clothing to a sleek charcoal business suit, crisp white collar, keeping exact facial identity, hair, and posture unchanged"
    ),
    SpecialistEditAction.REMOVE_UNWANTED_OBJECT: (
        "Remove the unwanted object in the background cleanly, seamless texture fill, natural lighting"
    ),
    SpecialistEditAction.REPAIR_BACKGROUND: (
        "Repair background, smooth clean neutral studio backdrop with soft gradient, subject unchanged"
    ),
    SpecialistEditAction.DERIVE_ANGLE: (
        "Turn character to three-quarter left perspective, maintain identical facial features, clothing, and hairstyle"
    ),
    SpecialistEditAction.CORRECT_PROP: (
        "Replace the held object with a vintage leather-bound notebook, realistic hand interaction and grip"
    ),
    SpecialistEditAction.MATERIAL_SWAP: (
        "Change jacket material from fabric to weathered dark brown leather with natural creases and specular highlights"
    ),
}


class SpecialistEditor:
    """Specialist Still Editor for Qwen-Image-Edit-2511 INT8 controlled operations."""

    def __init__(self):
        self.workflows_dir = os.path.abspath("workflows/api_format")

    def get_source_asset(self, asset_id: str) -> Optional[AssetRecord]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
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
                metadata_json=json.loads(row["metadata_json"] or "{}"),
                provenance_json=json.loads(row["provenance_json"] or "{}"),
                created_at=row["created_at"],
            )
        finally:
            conn.close()

    def create_edit_job(self, req: SpecialistEditRequest) -> SpecialistEditResponse:
        """Create and queue a specialist image edit job."""
        source_asset = self.get_source_asset(req.source_asset_id)
        if not source_asset:
            raise ValueError(f"Source asset not found: {req.source_asset_id}")

        wf_name = ACTION_WORKFLOW_MAP.get(req.action)
        if not wf_name:
            raise ValueError(f"Unsupported action: {req.action}")

        wf_path = os.path.join(self.workflows_dir, f"{wf_name}.json")
        if not os.path.exists(wf_path):
            raise FileNotFoundError(f"Workflow template missing: {wf_path}")

        with open(wf_path, "r", encoding="utf-8") as f:
            prompt_graph = json.load(f)

        prompt_text = req.instruction or DEFAULT_INSTRUCTIONS[req.action]
        seed = req.seed or 1000

        # Parameterize prompt graph
        if "6" in prompt_graph:
            prompt_graph["6"]["inputs"]["image"] = source_asset.file_path
        if "7" in prompt_graph:
            prompt_graph["7"]["inputs"]["prompt"] = prompt_text
        if "10" in prompt_graph:
            prompt_graph["10"]["inputs"]["seed"] = seed

        # Target output asset id
        action_suffix = req.action.value.upper()
        output_asset_id = f"EDIT_{source_asset.id}_{action_suffix}_{seed}"

        # Enqueue durable job
        job = DurableQueue.enqueue(
            JobCreate(
                project_id=req.project_id,
                kind=JobKind.EDIT_REPAIR,
                priority=40,
                backend="comfyui",
                payload_json={
                    "action": req.action.value,
                    "source_asset_id": req.source_asset_id,
                    "output_asset_id": output_asset_id,
                    "workflow_template": wf_name,
                    "prompt_text": prompt_text,
                    "seed": seed,
                    "prompt_graph": prompt_graph,
                },
            )
        )

        provenance = {
            "source_asset_id": req.source_asset_id,
            "source_asset_kind": source_asset.kind,
            "action": req.action.value,
            "workflow_template": wf_name,
            "model_architecture": "qwen_image_edit_2511_int8_convrot",
            "text_encoder": "qwen_2.5_vl_7b_fp8_scaled",
            "vae": "qwen_image_vae",
            "lora": "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16",
            "seed": seed,
            "job_id": job.id,
            "created_at": datetime.utcnow().isoformat(),
        }

        return SpecialistEditResponse(
            edit_job_id=job.id,
            action=req.action.value,
            source_asset_id=req.source_asset_id,
            output_asset_id=output_asset_id,
            status=job.status.value,
            prompt=prompt_text,
            seed=seed,
            provenance_json=provenance,
        )

    @staticmethod
    def _registered_name(node_type: str, field: str, basename: str) -> str:
        info = comfy_request(f"/object_info/{node_type}")
        names = info[node_type]["input"]["required"][field][0]
        matches = [name for name in names if name.replace("\\", "/").split("/")[-1] == basename]
        if not matches:
            raise RuntimeError(f"ComfyUI cannot find required model component {basename}")
        return matches[0]

    def execute_edit(self, req: SpecialistEditRequest, timeout_s: int = 2400) -> AssetRecord:
        """Run a real Qwen Image Edit workflow and register its measured result."""
        with gpu_render_lease("qwen_edit"):
            return self._execute_edit_locked(req, timeout_s)

    def _execute_edit_locked(self, req: SpecialistEditRequest, timeout_s: int) -> AssetRecord:
        source = self.get_source_asset(req.source_asset_id)
        if not source:
            raise ValueError(f"Source asset not found: {req.source_asset_id}")
        source_path = Path(source.file_path).resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Source image is missing: {source_path}")

        workflow_name = ACTION_WORKFLOW_MAP[req.action]
        workflow_path = Path(self.workflows_dir) / f"{workflow_name}.json"
        with workflow_path.open("r", encoding="utf-8") as handle:
            workflow = json.load(handle)

        project_root = Path(__file__).resolve().parents[2]
        comfy_input = project_root / "services" / "comfyui" / "ComfyUI" / "input"
        comfy_output = project_root / "services" / "comfyui" / "ComfyUI" / "output"
        staged_name = f"studio_qwen_{uuid.uuid4().hex}{source_path.suffix}"
        staged_path = comfy_input / staged_name
        output_prefix = f"studio_qwen/{uuid.uuid4().hex}"
        prompt_text = req.instruction or DEFAULT_INSTRUCTIONS[req.action]
        seed = req.seed or 1000

        queue = comfy_request("/queue")
        if queue.get("queue_running") or queue.get("queue_pending"):
            raise RuntimeError("ComfyUI is busy; wait for the active render before editing an image.")
        shutil.copy2(source_path, staged_path)
        try:
            comfy_request("/free", {"unload_models": True, "free_memory": True})
            workflow["1"]["inputs"]["unet_name"] = self._registered_name(
                "UNETLoader", "unet_name", "qwen_image_edit_2511_int8_convrot.safetensors"
            )
            workflow["2"]["inputs"]["clip_name"] = self._registered_name(
                "CLIPLoader", "clip_name", "qwen_2.5_vl_7b_fp8_scaled.safetensors"
            )
            workflow["2"]["inputs"]["device"] = "cpu"
            workflow["3"]["inputs"]["vae_name"] = self._registered_name(
                "VAELoader", "vae_name", "qwen_image_vae.safetensors"
            )
            workflow["4"]["inputs"]["lora_name"] = self._registered_name(
                "LoraLoaderModelOnly", "lora_name", "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors"
            )
            workflow["6"]["inputs"]["image"] = staged_name
            workflow["7"]["inputs"]["prompt"] = prompt_text
            workflow["10"]["inputs"]["seed"] = seed
            workflow["12"]["inputs"]["filename_prefix"] = output_prefix

            prompt_id = comfy_request("/prompt", {"prompt": workflow})["prompt_id"]
            deadline = time.monotonic() + timeout_s
            rendered = None
            while time.monotonic() < deadline:
                history = comfy_request(f"/history/{prompt_id}").get(prompt_id)
                if history:
                    status = history.get("status", {})
                    if status.get("status_str") == "error":
                        raise RuntimeError(f"Qwen edit failed: {status.get('messages', [])}")
                    for node_output in history.get("outputs", {}).values():
                        for image in node_output.get("images", []):
                            candidate = comfy_output / image.get("subfolder", "") / image["filename"]
                            if candidate.exists():
                                rendered = candidate
                    if rendered:
                        break
                time.sleep(2.0)
            if rendered is None:
                comfy_request("/queue", {"delete": [prompt_id]})
                raise TimeoutError("Qwen image edit timed out in ComfyUI")

            extractor = DINOExtractor()
            evaluations = extractor.evaluate_candidates([str(rendered)], ref_char_path=str(source_path))
            identity_score = evaluations[0]["raw_scores"]["whole_subject_similarity"]
            output_asset_id = f"EDIT_{source.id}_{req.action.value.upper()}_{seed}"
            return self.register_completed_edit_asset(
                project_id=req.project_id,
                output_asset_id=output_asset_id,
                source_asset_id=source.id,
                action=req.action,
                image_path=str(rendered),
                instruction=prompt_text,
                seed=seed,
                qa_metrics={
                    "identity_similarity": identity_score,
                    "evaluation": "REVIEW_REQUIRED" if identity_score < 0.82 else "DINO_PASS_SEMANTIC_REVIEW_REQUIRED",
                    "semantic_qa": "not_run",
                },
            )
        finally:
            staged_path.unlink(missing_ok=True)

    def register_completed_edit_asset(
        self,
        project_id: str,
        output_asset_id: str,
        source_asset_id: str,
        action: SpecialistEditAction,
        image_path: str,
        instruction: str,
        seed: int,
        qa_metrics: Optional[Dict[str, Any]] = None,
    ) -> AssetRecord:
        """Register completed edited asset with full provenance and QA metrics."""
        now = datetime.utcnow().isoformat()
        conn = get_connection()
        try:
            cursor = conn.cursor()

            # Ensure projects directory exists
            proj_dir = os.path.join(settings.paths.projects, project_id, "assets", "edits")
            os.makedirs(proj_dir, exist_ok=True)
            stored_path = os.path.join(proj_dir, f"{output_asset_id}.png")

            # Copy image if not already at destination
            if os.path.abspath(image_path) != os.path.abspath(stored_path):
                shutil.copy2(image_path, stored_path)

            qa_data = qa_metrics or {"evaluation": "NOT_EVALUATED"}

            provenance = {
                "parent_asset_id": source_asset_id,
                "action": action.value,
                "model": "qwen_image_edit_2511_int8_convrot",
                "instruction": instruction,
                "seed": seed,
                "qa_metrics": qa_data,
                "registered_at": now,
            }

            cursor.execute(
                """
                INSERT OR REPLACE INTO assets (id, project_id, tier, kind, version, name, file_path, metadata_json, provenance_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    output_asset_id,
                    project_id,
                    1,
                    AssetKind.EDITED_ASSET.value,
                    "V001",
                    f"Edit: {action.value}",
                    stored_path,
                    json.dumps({"action": action.value, "seed": seed, "instruction": instruction}),
                    json.dumps(provenance),
                    now,
                ),
            )
            conn.commit()

            return AssetRecord(
                id=output_asset_id,
                project_id=project_id,
                tier=1,
                kind=AssetKind.EDITED_ASSET.value,
                version="V001",
                name=f"Edit: {action.value}",
                file_path=stored_path,
                metadata_json={"action": action.value, "seed": seed, "instruction": instruction},
                provenance_json=provenance,
                created_at=now,
            )
        finally:
            conn.close()

    def list_edits_for_asset(self, source_asset_id: str) -> List[AssetRecord]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM assets WHERE json_extract(provenance_json, '$.parent_asset_id') = ? ORDER BY created_at ASC",
                (source_asset_id,),
            )
            rows = cursor.fetchall()
            return [
                AssetRecord(
                    id=r["id"],
                    project_id=r["project_id"],
                    tier=r["tier"],
                    kind=r["kind"],
                    version=r["version"],
                    name=r["name"],
                    file_path=r["file_path"],
                    metadata_json=json.loads(r["metadata_json"] or "{}"),
                    provenance_json=json.loads(r["provenance_json"] or "{}"),
                    created_at=r["created_at"],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def list_source_assets(self, limit: int = 100) -> List[AssetRecord]:
        """Return recent local image assets that can be used as Qwen edit sources."""
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM assets ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 500)),)
            ).fetchall()
            sources = []
            for row in rows:
                path = Path(row["file_path"])
                if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"} or not path.exists():
                    continue
                sources.append(AssetRecord(
                    id=row["id"], project_id=row["project_id"], tier=row["tier"], kind=row["kind"],
                    version=row["version"], name=row["name"], file_path=row["file_path"],
                    metadata_json=json.loads(row["metadata_json"] or "{}"),
                    provenance_json=json.loads(row["provenance_json"] or "{}"), created_at=row["created_at"],
                ))
            return sources
        finally:
            conn.close()
