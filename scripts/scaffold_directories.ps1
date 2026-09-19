# Scaffold full Studio OS directory structure

$root = "C:\Users\nikhi\Preeti_Studio"
Set-Location $root

$dirs = @(
    "models/image", "models/video", "models/audio", "models/tts", "models/lipsync", "models/upscalers", "models/qa", "models/llm",
    "services/comfyui", "services/wangp", "services/tts", "services/lipsync", "services/qa", "services/music",
    "workflows/upstream/comfy_official", "workflows/upstream/model_authors", "workflows/upstream/community",
    "workflows/studio", "workflows/api_format", "workflows/tests",
    "shared_assets/motion_library", "shared_assets/music_library", "shared_assets/sfx_library", "shared_assets/thumbnail_templates",
    "projects", "cache", "logs", "temp", "database/migrations"
)

foreach ($d in $dirs) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
    }
    $gitkeep = Join-Path $d ".gitkeep"
    if (-not (Test-Path $gitkeep)) {
        Set-Content -Path $gitkeep -Value "" -NoNewline
    }
}

Write-Host "All Studio OS directories successfully scaffolded."
