import os
import sys
import json
import argparse
from pathlib import Path
from PIL import Image
import torch
from transformers import AutoImageProcessor, AutoModel

MODEL_DIR = Path("models/qa/dino/dinov2-small")

_processor = None
_model = None
_device = None

def get_model(device_name=None):
    global _processor, _model, _device
    if _model is None:
        if device_name is None:
            # CPU is fast (<40ms) and keeps GPU 100% free for diffusion/video tasks
            _device = torch.device("cuda" if torch.cuda.is_available() and False else "cpu")
        else:
            _device = torch.device(device_name)
        _processor = AutoImageProcessor.from_pretrained(str(MODEL_DIR))
        _model = AutoModel.from_pretrained(str(MODEL_DIR)).to(_device)
        _model.eval()
    return _processor, _model, _device

def extract_embedding(image_path: str, crop_box: tuple = None, device_name: str = "cpu") -> list:
    processor, model, dev = get_model(device_name)
    img = Image.open(image_path).convert("RGB")
    if crop_box:
        # crop_box = (left, upper, right, lower)
        w, h = img.size
        # Handle normalized coordinates [0.0 - 1.0] if all values <= 1.0
        if all(0.0 <= v <= 1.0 for v in crop_box):
            box = (int(crop_box[0] * w), int(crop_box[1] * h), int(crop_box[2] * w), int(crop_box[3] * h))
        else:
            box = tuple(map(int, crop_box))
        img = img.crop(box)

    inputs = processor(images=img, return_tensors="pt").to(dev)
    with torch.no_grad():
        outputs = model(**inputs)
        # CLS token is at index 0 of last_hidden_state
        cls_emb = outputs.last_hidden_state[:, 0, :]
        cls_emb = torch.nn.functional.normalize(cls_emb, p=2, dim=-1)
    return cls_emb.cpu().squeeze(0).tolist()

def cosine_similarity(v1: list, v2: list) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    return float(max(-1.0, min(1.0, dot)))

def evaluate_candidate(candidate_path: str, ref_char_path: str = None, ref_loc_path: str = None,
                       char_crop: tuple = None, bg_crop: tuple = None, device_name: str = "cpu") -> dict:
    cand_whole_emb = extract_embedding(candidate_path, device_name=device_name)
    
    char_sim = 1.0
    crop_sim = 1.0
    loc_sim = 1.0
    style_sim = 1.0

    if ref_char_path and os.path.exists(ref_char_path):
        ref_char_whole = extract_embedding(ref_char_path, device_name=device_name)
        char_sim = cosine_similarity(cand_whole_emb, ref_char_whole)
        
        # Identity crop
        cand_crop_emb = extract_embedding(candidate_path, crop_box=char_crop or (0.2, 0.1, 0.8, 0.7), device_name=device_name)
        ref_crop_emb = extract_embedding(ref_char_path, crop_box=char_crop or (0.2, 0.1, 0.8, 0.7), device_name=device_name)
        crop_sim = cosine_similarity(cand_crop_emb, ref_crop_emb)

    if ref_loc_path and os.path.exists(ref_loc_path):
        ref_loc_emb = extract_embedding(ref_loc_path, device_name=device_name)
        # Background crop (e.g. outer perimeter or upper region)
        cand_bg_emb = extract_embedding(candidate_path, crop_box=bg_crop or (0.0, 0.0, 1.0, 0.4), device_name=device_name)
        loc_sim = cosine_similarity(cand_bg_emb, ref_loc_emb)

    # Style similarity captures overall color / texture representation
    style_sim = (char_sim + crop_sim) / 2.0

    # Composite normalized score (weighted combination calibrated to 0.0 - 1.0)
    # Cosine sim for natural images typically ranges from 0.40 (unrelated) to 1.0 (identical)
    def calibrate(sim):
        return max(0.0, min(1.0, (sim - 0.40) / 0.60))

    norm_char = calibrate(char_sim)
    norm_crop = calibrate(crop_sim)
    norm_loc = calibrate(loc_sim)
    norm_style = calibrate(style_sim)

    # Weights: Identity/Crop 50%, Location 30%, Style 20%
    composite = (0.30 * norm_char) + (0.20 * norm_crop) + (0.30 * norm_loc) + (0.20 * norm_style)

    return {
        "candidate_path": str(candidate_path),
        "raw_scores": {
            "whole_subject_similarity": round(char_sim, 4),
            "identity_crop_similarity": round(crop_sim, 4),
            "location_similarity": round(loc_sim, 4),
            "style_similarity": round(style_sim, 4)
        },
        "normalized_scores": {
            "character_identity": round(norm_char, 4),
            "identity_crop": round(norm_crop, 4),
            "location": round(norm_loc, 4),
            "style": round(norm_style, 4),
            "composite": round(composite, 4)
        },
        "embedding": cand_whole_emb
    }

def main():
    parser = argparse.ArgumentParser(description="DINOv2 Visual QA Embedding & Similarity Extractor")
    parser.add_argument("--action", choices=["extract", "evaluate_candidates"], default="extract")
    parser.add_argument("--image", type=str, help="Path to single image for embedding")
    parser.add_argument("--crop", type=str, default="", help="Normalized crop x1,y1,x2,y2")
    parser.add_argument("--ref-char", type=str, default="", help="Path to canonical character reference")
    parser.add_argument("--ref-loc", type=str, default="", help="Path to canonical location reference")
    parser.add_argument("--candidates", nargs="*", default=[], help="Paths to candidate images")
    parser.add_argument("--batch-file", type=str, default="", help="JSON file with evaluation payload")
    parser.add_argument("--device", type=str, default="cpu")

    args = parser.parse_args()

    crop_box = None
    if args.crop:
        crop_box = [float(v.strip()) for v in args.crop.split(",")]

    if args.action == "extract":
        if not args.image:
            print(json.dumps({"error": "--image required for extract"}))
            sys.exit(1)
        emb = extract_embedding(args.image, crop_box=crop_box, device_name=args.device)
        print(json.dumps({"dim": len(emb), "embedding": emb}))

    elif args.action == "evaluate_candidates":
        cand_list = list(args.candidates)
        ref_char = args.ref_char
        ref_loc = args.ref_loc

        if args.batch_file and os.path.exists(args.batch_file):
            with open(args.batch_file, "r") as f:
                data = json.load(f)
                cand_list = data.get("candidates", cand_list)
                ref_char = data.get("ref_char", ref_char)
                ref_loc = data.get("ref_loc", ref_loc)

        results = []
        for cand in cand_list:
            res = evaluate_candidate(cand, ref_char_path=ref_char, ref_loc_path=ref_loc, device_name=args.device)
            results.append(res)

        print(json.dumps({"evaluations": results}))

if __name__ == "__main__":
    main()
