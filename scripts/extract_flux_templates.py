import json
import os
import shutil
import comfyui_workflow_templates as cwt
from comfyui_workflow_templates_core import get_asset_path

target_templates = [
    "image_flux2_klein_text_to_image",
    "image_flux2_klein_image_edit_4b_distilled",
]

upstream_dir = os.path.abspath("workflows/upstream/comfy_official")
os.makedirs(upstream_dir, exist_ok=True)

for t in cwt.iter_templates():
    if t.template_id in target_templates:
        print(f"\n=====================================")
        print(f"Template ID: {t.template_id}")
        print(f"Bundle: {t.bundle}, Version: {t.version}")
        for a in t.assets:
            src = get_asset_path(t.template_id, a.filename)
            dst = os.path.join(upstream_dir, a.filename)
            print(f"Asset: {a.filename}")
            print(f"  Source: {src}")
            print(f"  SHA256: {a.sha256}")
            if src and os.path.exists(src):
                shutil.copy2(src, dst)
                print(f"  Copied to: {dst}")
                if a.filename.endswith(".json"):
                    with open(dst, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    print(f"  JSON keys: {list(data.keys())[:10]}")
                    # Look for model loader nodes or widget values
                    nodes = data.get("nodes", []) if isinstance(data, dict) else []
                    print(f"  Nodes count: {len(nodes)}")
                    for node in nodes:
                        ntype = node.get("type", "")
                        widgets = node.get("widgets_values", [])
                        if any(k in ntype.lower() for k in ["loader", "checkpoint", "unet", "diffusion", "clip", "vae"]):
                            print(f"    Node: {ntype} (id {node.get('id')}) -> {widgets}")
