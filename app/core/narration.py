"""Turn reviewed narration into editable shots without rewriting the source."""
import re
from typing import Any, Dict, List


def plan_narration(text: str, target_duration_s: float) -> List[Dict[str, Any]]:
    """Keep paragraphs in order, splitting long passages at sentence/word boundaries.

    This is a literal narration planner, not an adaptation or translation model.
    Visual prompts are starting points for the shot editor.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    if not paragraphs:
        raise ValueError("Please enter narration containing text.")
    shots = []
    for paragraph_number, paragraph in enumerate(paragraphs, start=1):
        # split() changes whitespace only; quotes, colons and Devanagari survive.
        words = paragraph.split()
        chunks, current = [], ""
        for word in words:
            if current and len(current) + len(word) + 1 > 240:
                chunks.append(current)
                current = ""
            current = f"{current} {word}".strip()
            if len(current) >= 120 and re.search(r"[.!?।][\"'”’]?$", word):
                chunks.append(current)
                current = ""
        if current:
            chunks.append(current)
        for chunk_index, chunk in enumerate(chunks, start=1):
            shots.append({
                "shot_id": f"narration_{paragraph_number:02d}_{chunk_index:02d}",
                "beat_number": paragraph_number,
                "heading": f"Story moment {paragraph_number}",
                "action": f"Illustrate this story moment: {chunk}",
                "speaker": "NARRATOR",
                "dialogue_line": chunk,
                "framing": "medium" if chunk_index == 1 else "medium_close_up",
                "engine": "2.5d",
            })
    weight = sum(len(s["dialogue_line"]) for s in shots)
    remaining = max(0.0, target_duration_s - len(shots))
    for shot in shots:
        shot["duration_s"] = 1.0 + remaining * len(shot["dialogue_line"]) / weight
    return shots
