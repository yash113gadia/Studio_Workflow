import json
import os

workflow_path = "workflows/upstream/comfy_official/image_qwen_image_edit_2511_int8.json"
with open(workflow_path, "r", encoding="utf-8") as f:
    data = json.load(f)

print("Top-level nodes:")
for n in data.get("nodes", []):
    nid = n.get("id")
    ntype = n.get("type")
    title = n.get("title", "")
    widgets = n.get("widgets_values", [])
    print(f"  Node {nid}: {ntype} ({title})")
    if ntype == "MarkdownNote":
        text = widgets[0] if widgets else ""
        print(f"    Note content:\n{text.encode('ascii', errors='replace').decode('ascii')}")
    elif widgets:
        print(f"    Widgets: {widgets}")

print("\nSubgraphs:")
for sg in data.get("definitions", {}).get("subgraphs", []):
    sg_name = sg.get("name", "")
    sg_id = sg.get("id", "")
    print(f"\n--- Subgraph: {sg_name} ({sg_id}) ---")
    for n in sg.get("nodes", []):
        nid = n.get("id")
        ntype = n.get("type")
        title = n.get("title", "")
        widgets = n.get("widgets_values", [])
        if any(k in ntype.lower() for k in ["loader", "checkpoint", "unet", "diffusion", "clip", "vae", "model", "sampler", "qwen", "edit", "convrot"]):
            print(f"    SubNode {nid}: {ntype} ({title}) -> {widgets}")
