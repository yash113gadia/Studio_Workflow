import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

class DINOExtractor:
    """Interface for extracting DINO visual embeddings and candidate scoring components."""

    def __init__(self, python_path: str = None, script_path: str = None):
        if python_path is None:
            # Use comfy_env where PyTorch and Transformers are installed
            base_dir = Path(__file__).resolve().parent.parent.parent.parent
            self.python_path = str(base_dir / "environments" / "comfy_env" / "Scripts" / "python.exe")
        else:
            self.python_path = python_path

        if script_path is None:
            base_dir = Path(__file__).resolve().parent.parent.parent.parent
            self.script_path = str(base_dir / "scripts" / "visual_qa_extractor.py")
        else:
            self.script_path = script_path

    def extract(self, image_path: str, crop: Optional[tuple] = None, device: str = "cpu") -> List[float]:
        """Extract a 384-dimensional DINO visual embedding for an image or image crop."""
        cmd = [
            self.python_path,
            self.script_path,
            "--action", "extract",
            "--image", str(image_path),
            "--device", device
        ]
        if crop:
            crop_str = ",".join(str(v) for v in crop)
            cmd.extend(["--crop", crop_str])

        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        # Parse stdout (last line with JSON)
        lines = [line.strip() for line in proc.stdout.strip().splitlines() if line.strip()]
        for line in reversed(lines):
            try:
                data = json.loads(line)
                if "embedding" in data:
                    return data["embedding"]
            except Exception:
                continue
        raise RuntimeError(f"Failed to extract embedding: {proc.stderr or proc.stdout}")

    def evaluate_candidates(
        self,
        candidate_paths: List[str],
        ref_char_path: Optional[str] = None,
        ref_loc_path: Optional[str] = None,
        device: str = "cpu"
    ) -> List[Dict[str, Any]]:
        """Evaluate a batch of candidate images against reference character and location."""
        cmd = [
            self.python_path,
            self.script_path,
            "--action", "evaluate_candidates",
            "--device", device,
            "--candidates"
        ]
        cmd.extend(candidate_paths)

        if ref_char_path:
            cmd.extend(["--ref-char", str(ref_char_path)])
        if ref_loc_path:
            cmd.extend(["--ref-loc", str(ref_loc_path)])

        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = [line.strip() for line in proc.stdout.strip().splitlines() if line.strip()]
        for line in reversed(lines):
            try:
                data = json.loads(line)
                if "evaluations" in data:
                    return data["evaluations"]
            except Exception:
                continue
        raise RuntimeError(f"Failed to evaluate candidates: {proc.stderr or proc.stdout}")

    @staticmethod
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        """Compute cosine similarity between two unit-normalized vectors."""
        dot = sum(a * b for a, b in zip(v1, v2))
        return float(max(-1.0, min(1.0, dot)))
