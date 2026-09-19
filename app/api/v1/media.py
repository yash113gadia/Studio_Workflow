"""Media Streaming & Asset Serving Router for Preeti Studio Web UI."""
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

router = APIRouter(prefix="/media", tags=["Media"])
STUDIO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


@router.get("/stream")
def stream_media(path: str = Query(..., description="Absolute or relative path to media file")):
    """Streams a local video, image, or audio file directly to the browser."""
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = STUDIO_ROOT / file_path

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")

    ext = file_path.suffix.lower()
    media_types = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".srt": "text/plain",
        ".json": "application/json",
    }
    media_type = media_types.get(ext, "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name,
    )


@router.get("/gallery")
def list_gallery_videos():
    """Lists all generated master videos for the web UI gallery."""
    projects_dir = STUDIO_ROOT / "projects"
    videos = []
    if projects_dir.exists():
        for mp4 in projects_dir.rglob("master_*.mp4"):
            stat = mp4.stat()
            parent = mp4.parent
            provenance_file = list(parent.glob("*.provenance.json"))
            title = mp4.stem.replace("master_", "").replace("_1080x1920", "")
            
            # Look for thumbnail
            thumb_path = None
            thumbs_dir = parent / "thumbnails"
            if thumbs_dir.exists():
                thumbs = list(thumbs_dir.glob("*.jpg"))
                if thumbs:
                    thumb_path = str(thumbs[0])

            videos.append({
                "title": title,
                "video_path": str(mp4),
                "thumbnail_path": thumb_path,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_time": stat.st_mtime,
                "stream_url": f"/api/v1/media/stream?path={str(mp4)}",
                "thumb_url": f"/api/v1/media/stream?path={thumb_path}" if thumb_path else None,
            })

    # Sort newest first
    videos.sort(key=lambda x: x["created_time"], reverse=True)
    return {"videos": videos}
