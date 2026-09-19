import sys, os
sys.path.insert(0, os.path.abspath("services/comfyui/ComfyUI"))
import nodes


node_classes = [
    "UNETLoader", "CLIPLoader", "VAELoader", "CLIPTextEncode",
    "EmptyFlux2LatentImage", "CFGGuider", "KSamplerSelect",
    "Flux2Scheduler", "SamplerCustomAdvanced", "RandomNoise",
    "VAEDecode", "SaveImage", "LoadImage", "VAEEncode",
    "Flux2ReferenceConditioning"
]

print("Verifying ComfyUI Node Classes:")
for nc in node_classes:
    if nc in nodes.NODE_CLASS_MAPPINGS:
        cls = nodes.NODE_CLASS_MAPPINGS[nc]
        print(f"  [OK] {nc} -> inputs: {list(cls.INPUT_TYPES().get('required', {}).keys())}")
    else:
        print(f"  [MISSING] {nc}")
