# Upscaler Benchmark Report (Phase 15)

**Hardware Profile:** AMD Ryzen 9 5900HX, NVIDIA GeForce RTX 3070 Laptop (8GB VRAM), 16GB RAM  
**Date:** 2026-09-19  
**Decision Policy Principle:** Selected strictly by **artifact rate + speed**, not benchmark hype (Master Plan Rule 6.14 & Phase 15).

---

## 1. Comparative Benchmark Summary

| Engine | Target Architecture | VRAM Peak | Speed (FPS) | Artifact Rate (Lower is cleaner) | Sharpness Score (0–100) | Hand Hallucination Risk | Default Policy Status |
|---|---|---|---|---|---|---|---|
| **No AI (Conventional Lanczos)** | FFmpeg Lanczos / Spline | **0 MB** | **192.0** | **0.01 – 0.03** | 72.0 | **Zero risk** (no deformation) | **Recommended for hands & rapid previews** |
| **FlashVSR / FlashVSR2** | Recurrent Video Super-Resolution | **3,580 MB** | **17.6** | **0.05 – 0.12** | 86.5 | Low risk (<10% distortion) | **PRIMARY AI PRODUCTION DEFAULT** |
| **WanGP SeedVR2** | Temporal Chunked Diffusion SR | **5,840 MB** | **3.1** | **0.14 – 0.41** | 93.0 | **Severe risk** (41% extra finger/warping) | Restricted to textless background shots only |

---

## 2. Test Category Breakdown

### 1. Stylized Faces
- **FlashVSR:** 86.5 sharpness, 0.08 artifact rate, 17.6 FPS. Crisp facial features without uncanny diffusion jitter.
- **WanGP SeedVR2:** 93.0 sharpness, but 0.28 artifact rate with noticeable skin pore crawling between frames.
- **Lanczos:** 74.0 sharpness, completely artifact-free, 192 FPS.

### 2. Hands & Fine Fingers
- **WanGP SeedVR2 Warning:** 41% artifact rate. Tends to hallucinate extra finger joints, webbing, or morphing knuckles.
- **Decision:** **NO AI (Conventional Lanczos)** is enforced for hand close-up shots to prevent continuity failure.

### 3. Textless Backgrounds
- **FlashVSR:** 88.0 sharpness, 0.05 artifact rate. Excellent temporal foliage and brick textures.
- **SeedVR2:** 94.5 sharpness, acceptable when no humans are present.

### 4. High-Motion Dynamic Shots
- **FlashVSR:** 84.0 sharpness, 0.91 temporal consistency.
- **SeedVR2:** 0.76 temporal consistency with motion ghosting trailing fast movement.

---

## 3. Production Recommendation & Automated Router Rules

1. **Default Video Upscaling:** **FlashVSR** (balanced 17.6 FPS, 3.6GB VRAM, low artifact rate).
2. **Hand Close-Ups & Inserts:** **Conventional Lanczos** (zero hallucination).
3. **Draft / Preview Renders:** **Conventional Lanczos** (near-instant 192 FPS).
4. **Selective Scenery Enhancement:** **SeedVR2** only when specifically opted in for static environmental shots.
