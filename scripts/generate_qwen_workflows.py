"""Generate official ComfyUI API workflows for Qwen-Image-Edit-2511 INT8 specialist actions."""
import json
import os

SPECIALIST_ACTIONS = {
    "qwen_edit_outfit_v001": {
        "action": "preserve_identity_change_outfit",
        "description": "Change outfit/clothing while preserving character identity and facial geometry",
        "default_prompt": "Change the character's clothing to a sleek charcoal business suit, crisp white collar, keeping exact facial identity, hair, and posture unchanged",
        "prefix": "qwen_outfit"
    },
    "qwen_edit_remove_object_v001": {
        "action": "remove_unwanted_object",
        "description": "Remove an unwanted object or artifact cleanly while seamlessly blending background",
        "default_prompt": "Remove the unwanted object in the background cleanly, seamless texture fill, natural lighting",
        "prefix": "qwen_rm_obj"
    },
    "qwen_edit_repair_bg_v001": {
        "action": "repair_background",
        "description": "Repair background defects, noise, or artifacts without altering foreground subject",
        "default_prompt": "Repair background, smooth clean neutral studio backdrop with soft gradient, subject unchanged",
        "prefix": "qwen_repair_bg"
    },
    "qwen_edit_derive_angle_v001": {
        "action": "derive_angle",
        "description": "Derive a new perspective or angle of the character with high facial consistency",
        "default_prompt": "Turn character to three-quarter left perspective, maintain identical facial features, clothing, and hairstyle",
        "prefix": "qwen_angle"
    },
    "qwen_edit_correct_prop_v001": {
        "action": "correct_prop",
        "description": "Replace, adjust, or correct an in-hand prop or held accessory",
        "default_prompt": "Replace the held object with a vintage leather-bound notebook, realistic hand interaction and grip",
        "prefix": "qwen_prop"
    },
    "qwen_edit_material_swap_v001": {
        "action": "material_swap",
        "description": "Swap material or surface texture on clothing, props, or background surfaces",
        "default_prompt": "Change jacket material from fabric to weathered dark brown leather with natural creases and specular highlights",
        "prefix": "qwen_mat_swap"
    }
}


def build_qwen_edit_workflow(action_key, config):
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "diffusion_models\\qwen_image_edit_2511_int8_convrot.safetensors",
                "weight_dtype": "default"
            }
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "text_encoders\\qwen_2.5_vl_7b_fp8_scaled.safetensors",
                "type": "qwen_image"
            }
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "vae\\qwen_image_vae.safetensors"
            }
        },
        "4": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["1", 0],
                "lora_name": "loras\\Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors",
                "strength_model": 1.0
            }
        },
        "5": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {
                "model": ["4", 0],
                "shift": 3.1
            }
        },
        "6": {
            "class_type": "LoadImage",
            "inputs": {
                "image": "input_reference.png"
            }
        },
        "7": {
            "class_type": "TextEncodeQwenImageEditPlus",
            "inputs": {
                "clip": ["2", 0],
                "vae": ["3", 0],
                "image1": ["6", 0],
                "prompt": config["default_prompt"]
            }
        },
        "8": {
            "class_type": "TextEncodeQwenImageEditPlus",
            "inputs": {
                "clip": ["2", 0],
                "vae": ["3", 0],
                "image1": ["6", 0],
                "prompt": ""
            }
        },
        "9": {
            "class_type": "VAEEncode",
            "inputs": {
                "pixels": ["6", 0],
                "vae": ["3", 0]
            }
        },
        "10": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["5", 0],
                "positive": ["7", 0],
                "negative": ["8", 0],
                "latent_image": ["9", 0],
                "seed": 1000,
                "steps": 4,
                "cfg": 3.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0
            }
        },
        "11": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["10", 0],
                "vae": ["3", 0]
            }
        },
        "12": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["11", 0],
                "filename_prefix": config["prefix"]
            }
        }
    }


def main():
    target_dir = os.path.abspath("workflows/api_format")
    os.makedirs(target_dir, exist_ok=True)

    for action_key, config in SPECIALIST_ACTIONS.items():
        wf = build_qwen_edit_workflow(action_key, config)
        out_path = os.path.join(target_dir, f"{action_key}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=2)
        print(f"Generated: {out_path} ({config['action']})")


if __name__ == "__main__":
    main()
