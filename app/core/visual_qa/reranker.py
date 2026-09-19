import os
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.core.database import get_db_connection
from app.core.visual_qa.dino_extractor import DINOExtractor

class CandidateReranker:
    """Three-Candidate Reranking and QA Decision Policy Engine."""

    def __init__(
        self,
        extractor: Optional[DINOExtractor] = None,
        min_identity_threshold: float = 0.65,
        min_composite_threshold: float = 0.60
    ):
        self.extractor = extractor or DINOExtractor()
        self.min_identity_threshold = min_identity_threshold
        self.min_composite_threshold = min_composite_threshold

    def evaluate_and_rerank(
        self,
        project_id: str,
        candidate_paths: List[str],
        shot_id: Optional[str] = None,
        ref_char_path: Optional[str] = None,
        ref_loc_path: Optional[str] = None,
        character_id: Optional[str] = None,
        location_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Score 3 candidates, rank them, select winning candidate, and record raw/normalized components."""
        if not candidate_paths:
            raise ValueError("Candidate paths list cannot be empty")

        eval_results = self.extractor.evaluate_candidates(
            candidate_paths=candidate_paths,
            ref_char_path=ref_char_path,
            ref_loc_path=ref_loc_path
        )

        processed = []
        for idx, item in enumerate(eval_results):
            raw = item["raw_scores"]
            norm = item["normalized_scores"]
            comp_score = norm["composite"]

            rejections = []
            if ref_char_path and raw["whole_subject_similarity"] < self.min_identity_threshold:
                rejections.append(
                    f"REJECT_IDENTITY_DRIFT: identity similarity {raw['whole_subject_similarity']:.4f} < {self.min_identity_threshold}"
                )
            if comp_score < self.min_composite_threshold:
                rejections.append(
                    f"REJECT_LOW_COMPOSITE: composite score {comp_score:.4f} < {self.min_composite_threshold}"
                )

            is_passing = len(rejections) == 0
            cand_id = f"CAND_{idx+1:02d}_{uuid.uuid4().hex[:6].upper()}"

            processed.append({
                "candidate_id": cand_id,
                "candidate_path": item["candidate_path"],
                "raw_scores": raw,
                "normalized_scores": norm,
                "composite_score": comp_score,
                "is_passing": is_passing,
                "rejections": rejections
            })

        # Sort descending by composite score
        processed.sort(key=lambda x: x["composite_score"], reverse=True)

        winner_selected = False
        final_candidates = []
        now = datetime.utcnow().isoformat()
        conn = get_db_connection()
        cursor = conn.cursor()

        for rank, cand in enumerate(processed, start=1):
            if cand["is_passing"] and not winner_selected:
                status = "ACCEPTED"
                is_winner = True
                winner_selected = True
            elif cand["is_passing"]:
                status = "ALTERNATIVE"
                is_winner = False
            else:
                status = "REJECTED"
                is_winner = False

            cand_record = {
                **cand,
                "rank": rank,
                "status": status,
                "is_winner": is_winner
            }
            final_candidates.append(cand_record)

            # Persist to database
            eval_id = f"EVAL_{uuid.uuid4().hex[:12].upper()}"
            cursor.execute("""
                INSERT INTO candidate_evaluations (
                    id, project_id, shot_id, candidate_id, candidate_path,
                    character_id, location_id, raw_scores_json, normalized_scores_json,
                    composite_score, rank, status, is_winner, rejection_reasons_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                eval_id,
                project_id,
                shot_id or "",
                cand["candidate_id"],
                cand["candidate_path"],
                character_id or "",
                location_id or "",
                json.dumps(cand["raw_scores"]),
                json.dumps(cand["normalized_scores"]),
                cand["composite_score"],
                rank,
                status,
                1 if is_winner else 0,
                json.dumps(cand["rejections"]),
                now
            ))

        conn.commit()
        conn.close()

        winning_candidate = next((c for c in final_candidates if c["is_winner"]), None)

        return {
            "project_id": project_id,
            "shot_id": shot_id,
            "total_candidates": len(final_candidates),
            "status": "SUCCESS" if winning_candidate else "ALL_FAILED",
            "fallback_ladder_action": "NONE" if winning_candidate else "TRIGGER_CINEMATIC_FALLBACK_LADDER_ATTEMPT_2",
            "winner": winning_candidate,
            "candidates": final_candidates
        }
