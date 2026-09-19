import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.core.database import get_db_connection

class LongitudinalDriftTracker:
    """Tracks character identity consistency over episodes/scenes and raises drift warnings."""

    def __init__(self, drift_warning_delta: float = 0.15, window_size: int = 5):
        self.drift_warning_delta = drift_warning_delta
        self.window_size = window_size

    def record_shot_identity(
        self,
        project_id: str,
        character_id: str,
        similarity_to_canonical: float,
        shot_id: Optional[str] = None,
        scene_id: Optional[str] = None,
        episode_id: Optional[str] = None,
        candidate_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record a shot's identity similarity to Tier 0 and check for longitudinal drift."""
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch recent similarities
        cursor.execute("""
            SELECT similarity_to_canonical FROM qa_drift_logs
            WHERE project_id = ? AND character_id = ?
            ORDER BY created_at DESC LIMIT ?
        """, (project_id, character_id, self.window_size - 1))
        past_rows = cursor.fetchall()
        past_sims = [row["similarity_to_canonical"] for row in past_rows]

        all_sims = [similarity_to_canonical] + past_sims
        rolling_avg = sum(all_sims) / len(all_sims)

        # Baseline Tier 0 canonical is 1.0
        drift_delta = max(0.0, 1.0 - rolling_avg)
        flagged_warning = 1 if (drift_delta > self.drift_warning_delta or similarity_to_canonical < 0.70) else 0

        log_id = f"DRIFT_{uuid.uuid4().hex[:12].upper()}"
        now = datetime.utcnow().isoformat()

        cursor.execute("""
            INSERT INTO qa_drift_logs (
                id, project_id, character_id, episode_id, scene_id, shot_id,
                candidate_id, similarity_to_canonical, rolling_average,
                drift_delta, flagged_warning, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            log_id,
            project_id,
            character_id,
            episode_id or "",
            scene_id or "",
            shot_id or "",
            candidate_id or "",
            similarity_to_canonical,
            round(rolling_avg, 4),
            round(drift_delta, 4),
            flagged_warning,
            now
        ))
        conn.commit()
        conn.close()

        warning_message = None
        if flagged_warning:
            warning_message = (
                f"CHARACTER_IDENTITY_DRIFT_ALERT: Character '{character_id}' rolling similarity "
                f"{rolling_avg:.4f} has drifted {drift_delta:.4f} away from canonical Tier 0."
            )

        return {
            "log_id": log_id,
            "project_id": project_id,
            "character_id": character_id,
            "similarity_to_canonical": round(similarity_to_canonical, 4),
            "rolling_average": round(rolling_avg, 4),
            "drift_delta": round(drift_delta, 4),
            "flagged_warning": bool(flagged_warning),
            "warning_message": warning_message,
            "created_at": now
        }

    def get_drift_history(self, project_id: str, character_id: str) -> Dict[str, Any]:
        """Fetch historical drift trajectory for a character."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, episode_id, scene_id, shot_id, candidate_id,
                   similarity_to_canonical, rolling_average, drift_delta,
                   flagged_warning, created_at
            FROM qa_drift_logs
            WHERE project_id = ? AND character_id = ?
            ORDER BY created_at ASC
        """, (project_id, character_id))
        rows = cursor.fetchall()
        conn.close()

        history = [dict(row) for row in rows]
        has_active_warning = any(r["flagged_warning"] for r in history[-3:]) if history else False

        return {
            "project_id": project_id,
            "character_id": character_id,
            "total_records": len(history),
            "has_active_warning": has_active_warning,
            "history": history
        }
