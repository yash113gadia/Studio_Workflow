import os
import shutil
import comfyui_workflow_templates as cwt
from comfyui_workflow_templates_core import get_asset_path

print("Total templates registered:", len(list(cwt.iter_templates())))
all_ids = sorted([t.template_id for t in cwt.iter_templates()])
print(f"Total templates: {len(all_ids)}")
for tid in all_ids:
    if any(k in tid.lower() for k in ["flux", "klein", "image_", "wan", "minimax"]):
        print(f"  {tid}")

