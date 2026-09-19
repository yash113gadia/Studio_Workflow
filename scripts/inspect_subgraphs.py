import json

for fname in [
    "workflows/upstream/comfy_official/image_flux2_klein_text_to_image.json",
    "workflows/upstream/comfy_official/image_flux2_klein_image_edit_4b_distilled.json"
]:
    print("=" * 60)
    print("File:", fname)
    with open(fname, "r", encoding="utf-8") as f:
        d = json.load(f)
    subgraphs = d.get("definitions", {}).get("subgraphs", [])
    for sg in subgraphs:
        print(f"Subgraph: {sg.get('name')} (id {sg.get('id')})")
        for node in sg.get("nodes", []):
            ntype = node.get("type", "")
            w = node.get("widgets_values", [])
            title = node.get("title", "")
            if any(k in ntype.lower() for k in ["loader", "checkpoint", "diffusion", "clip", "vae", "unet"]):
                print(f"  Node: {ntype} [title: {title}] -> {w}")
