import os
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.core.database import get_db_connection
from app.core.visual_qa.dino_extractor import DINOExtractor

class CanonVisualRegistry:
    """Registry for storing and retrieving canonical visual reference embeddings."""

    def __init__(self, extractor: Optional[DINOExtractor] = None):
        self.extractor = extractor or DINOExtractor()

    def register_canonical_reference(
        self,
        project_id: str,
        entity_type: str,
        entity_id: str,
        image_path: str,
        sub_slot: str = "CANON_DEFAULT",
        asset_id: Optional[str] = None,
        crop: Optional[tuple] = None
    ) -> Dict[str, Any]:
        """Extract and store canonical DINO visual embedding for a character, wardrobe, or location."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Reference image not found: {image_path}")

        emb = self.extractor.extract(image_path, crop=crop)
        emb_id = f"EMB_{uuid.uuid4().hex[:12].upper()}"
        now = datetime.utcnow().isoformat()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO visual_embeddings (
                id, project_id, entity_type, entity_id, sub_slot,
                asset_id, model_name, dim, embedding_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            emb_id,
            project_id,
            entity_type,
            entity_id,
            sub_slot,
            asset_id or "",
            "dinov2-small",
            len(emb),
            json.dumps(emb),
            now
        ))
        conn.commit()
        conn.close()

        return {
            "embedding_id": emb_id,
            "project_id": project_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "sub_slot": sub_slot,
            "dim": len(emb),
            "created_at": now
        }

    def get_canonical_embedding(
        self,
        project_id: str,
        entity_type: str,
        entity_id: str,
        sub_slot: str = "CANON_DEFAULT"
    ) -> Optional[List[float]]:
        """Retrieve canonical embedding vector for a given entity."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT embedding_json FROM visual_embeddings
            WHERE project_id = ? AND entity_type = ? AND entity_id = ? AND sub_slot = ?
            ORDER BY created_at DESC LIMIT 1
        """, (project_id, entity_type, entity_id, sub_slot))
        row = cursor.fetchone()
        conn.close()

        if row:
            return json.loads(row["embedding_json"])
        return None
