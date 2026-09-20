"""Runtime capability discovery for the local studio.

An installed checkpoint is not the same as a connected or verified engine.  This
module keeps those states separate so the API and browser never advertise a
mock implementation as usable inference.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[2]
VERIFICATION_FILE = ROOT / "configs" / "engine_verification.json"


def _verification_overrides() -> Dict[str, Dict[str, Any]]:
    """Runtime verification results recorded by real smoke runs; they override the static defaults."""
    try:
        import json
        return json.loads(VERIFICATION_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _files(paths: Iterable[str]) -> List[Path]:
    return [ROOT / path for path in paths]


def _entry(
    engine_id: str,
    label: str,
    stage: str,
    paths: List[str],
    runtime: str,
    selectable: bool,
    backend: str,
    note: str,
    setup_hint: str = "",
) -> Dict[str, Any]:
    resolved = _files(paths)
    installed = bool(resolved) and all(path.exists() and path.stat().st_size > 1_000 for path in resolved)
    override = _verification_overrides().get(engine_id, {}) if installed else {}
    return {
        "id": engine_id,
        "label": label,
        "stage": stage,
        "backend": backend,
        "installed": installed,
        "runtime": override.get("runtime", runtime) if installed else "missing_weights",
        "selectable": bool(override.get("selectable", selectable)) and installed,
        "size_gib": round(sum(path.stat().st_size for path in resolved if path.exists()) / 1024**3, 2),
        "components": paths,
        "note": override.get("note", note) if installed else "Required local weights are not installed.",
        "setup_hint": setup_hint,
        "verified_at": override.get("verified_at"),
    }


def discover_capabilities() -> Dict[str, Any]:
    engines = [
        _entry(
            "flux2_klein", "FLUX.2 Klein 4B FP8", "image",
            ["models/image/diffusion_models/flux-2-klein-4b-fp8.safetensors",
             "models/image/text_encoders/qwen_3_4b.safetensors",
             "models/image/vae/flux2-vae.safetensors"],
            "verified", True, "ComfyUI", "Primary keyframe and artwork generator; real inference verified.",
        ),
        _entry(
            "qwen_image_edit", "Qwen Image Edit 2511 INT8", "image_edit",
            ["models/image/diffusion_models/qwen_image_edit_2511_int8_convrot.safetensors",
             "models/image/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors",
             "models/image/vae/qwen_image_vae.safetensors",
             "models/image/loras/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors"],
            "installed_unverified", True, "ComfyUI", "Weights are installed. First use may take time while ComfyUI loads the model. Click to try.",
        ),
        _entry(
            "ltx_video_095", "LTX-Video 2B 0.9.5", "video",
            ["models/video/ltx25/ltx-video-2b-v0.9.5.safetensors",
             "models/image/text_encoders/t5xxl_fp8_e4m3fn_scaled.safetensors"],
            "verified", True, "ComfyUI", "Real image-conditioned motion verified on this RTX 3070.",
        ),
        _entry(
            "minimax_h3", "MiniMax H3 Ref2VA INT8", "video",
            ["models/video/minimax_h3/MiniMax-H3-Ref2VA-pruned_int8_convrot.safetensors",
             "models/video/minimax_h3/MiniMax-H3-video_vae_fp16.safetensors",
             "models/video/minimax_h3/MiniMax-H3-audio_vae_fp32.safetensors",
             "models/video/minimax_h3/Qwen3-VL-32B-Instruct/qwen3vl-32B-MiniMax-H3-Q4_K_M.gguf"],
            "runtime_blocked", False, "WanGP", "Weights are present, but the WanGP environment is incomplete and has not passed inference.",
            setup_hint="Requires WanGP runtime. Install: pip install wangp-runtime in environments/wangp_env, then run scripts/verify_wangp.py",
        ),
        _entry(
            "scail2", "SCAIL-2 14B INT8", "performance",
            ["models/video/wan21/scail2_14B_quanto_mbf16_int8.safetensors",
             "models/video/wan21/Wan2.1_VAE.safetensors"],
            "runtime_blocked", False, "WanGP", "Weights are present; the controlled-performance runtime has not passed inference.",
            setup_hint="Requires WanGP runtime with SCAIL-2 adapter. Install wangp-runtime, then run scripts/verify_scail.py",
        ),
        _entry(
            "ace_step", "ACE-Step Music", "music",
            ["models/audio/ace_step/ace_step_transformer/diffusion_pytorch_model.safetensors",
             "models/audio/ace_step/music_dcae_f8c8/diffusion_pytorch_model.safetensors",
             "models/audio/ace_step/music_vocoder/diffusion_pytorch_model.safetensors"],
            "runtime_blocked", False, "WanGP", "Weights are present; the previous music endpoint produced placeholder bytes.",
            setup_hint="Requires ACE-Step neural music runtime. Install ace-step package and configure the music_engine adapter.",
        ),
        _entry(
            "dinov2", "DINOv2 Small", "visual_qa",
            ["models/qa/dino/dinov2-small/model.safetensors"],
            "verified", True, "Transformers", "Real local visual embeddings and similarity scoring.",
        ),
        _entry(
            "flashvsr", "FlashVSR 1.1", "upscale",
            ["models/upscalers/flashvsr/FlashVSR_v1.1_transformer_bf16.safetensors",
             "models/upscalers/flashvsr/FlashVSR_v1.1_tcdecoder_bf16.safetensors",
             "models/upscalers/flashvsr/FlashVSR_v1.1_lq_proj_bf16.safetensors"],
            "runtime_blocked", False, "WanGP", "Weights are present; current Studio code only performs conventional resizing.",
            setup_hint="Requires FlashVSR neural upscaler runtime. Install flashvsr package and configure the upscale adapter.",
        ),
        _entry(
            "film_interpolation", "FILM Frame Interpolation FP16", "frame_interpolation",
            ["models/upscalers/frame_interpolation/film_net_fp16.safetensors"],
            "verified", True, "ComfyUI", "Core FILM node and model verified on a short local clip; use 2x only after motion generation.",
        ),
        _entry(
            "chatterbox", "Chatterbox Multilingual", "voice",
            ["models/tts/chatterbox/t3_mtl23ls_v2.safetensors"],
            "missing_weights", False, "WanGP", "Neural TTS weights are not installed.",
            setup_hint="Download Chatterbox TTS weights from HuggingFace: models/tts/chatterbox/t3_mtl23ls_v2.safetensors",
        ),
        _entry(
            "musetalk", "MuseTalk 1.5", "lip_sync",
            ["models/lipsync/musetalk/models/musetalkV15/unet.pth"],
            "missing_weights", False, "MuseTalk", "Lip-sync weights and runtime are not installed.",
            setup_hint="Download MuseTalk 1.5 weights: models/lipsync/musetalk/models/musetalkV15/unet.pth",
        ),
        _entry(
            "hunyuan_foley", "HunyuanVideo-Foley XL", "foley",
            ["models/audio/hunyuan_foley"],
            "missing_weights", False, "Hunyuan Foley", "Generated Foley weights are not installed.",
            setup_hint="Download HunyuanVideo-Foley XL weights to models/audio/hunyuan_foley/",
        ),
    ]
    installed_components = []
    for base in (ROOT / "models").rglob("*"):
        if base.is_file() and base.stat().st_size > 50_000_000 and ".incomplete" not in base.name:
            installed_components.append({
                "path": str(base.relative_to(ROOT)).replace("\\", "/"),
                "size_gib": round(base.stat().st_size / 1024**3, 2),
            })
    return {
        "engines": engines,
        "summary": {
            "installed_weight_files": len(installed_components),
            "verified_engines": sum(engine["runtime"] == "verified" for engine in engines),
            "blocked_engines": sum(engine["runtime"] in {"runtime_blocked", "installed_unverified"} for engine in engines),
            "missing_engines": sum(engine["runtime"] == "missing_weights" for engine in engines),
            "free_disk_gib": round(shutil.disk_usage(ROOT).free / 1024**3, 1),
        },
        "installed_components": installed_components,
        "fallbacks": [
            {"id": "windows_sapi", "stage": "voice", "label": "Windows offline voices", "verified": True},
            {"id": "procedural_foley", "stage": "foley", "label": "Procedural/library Foley", "verified": True},
            {"id": "procedural_music", "stage": "music", "label": "Procedural ambient music", "verified": True},
            {"id": "lanczos", "stage": "upscale", "label": "Lanczos resize", "verified": True},
        ],
    }
