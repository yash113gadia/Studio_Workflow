"""Media Streaming & Asset Serving Router for Preeti Studio Web UI."""
import os
import uuid
import json
from urllib.parse import urlencode
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.asset_factory import AssetFactory
from app.core.database import get_connection
from app.core.models import AssetKind

router = APIRouter(prefix="/media", tags=["Media"])
STUDIO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

class DeleteImageRequest(BaseModel):
    path: str


@router.get("/stream")
def stream_media(path: str = Query(..., description="Absolute or relative path to media file")):
    """Streams a local video, image, or audio file directly to the browser."""
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = STUDIO_ROOT / file_path

    file_path = file_path.resolve()
    approved_roots = [
        (STUDIO_ROOT / "projects").resolve(),
        (STUDIO_ROOT / "cache").resolve(),
        (STUDIO_ROOT / "shared_assets").resolve(),
        (STUDIO_ROOT / "shared_assets" / "uploads").resolve(),
    ]
    if not any(file_path.is_relative_to(root) for root in approved_roots):
        raise HTTPException(status_code=403, detail="Media path is outside approved Studio output directories")

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
            
            mock_output = False
            for sidecar in provenance_file:
                try:
                    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
                    if metadata.get("qa_report", {}).get("overall_decision") == "MOCK":
                        mock_output = True
                    if metadata.get("title"):
                        title = metadata["title"]
                except (OSError, ValueError):
                    continue
            if mock_output:
                continue
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
                "stream_url": "/api/v1/media/stream?" + urlencode({"path": str(mp4)}),
                "thumb_url": "/api/v1/media/stream?" + urlencode({"path": thumb_path}) if thumb_path else None,
            })

    # Sort newest first
    videos.sort(key=lambda x: x["created_time"], reverse=True)
    return {"videos": videos}


@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    """Uploads an image to the shared assets directory."""
    if file.filename:
        ext = Path(file.filename).suffix.lower()
    else:
        ext = ".png"
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        raise HTTPException(status_code=400, detail="Only image files (.jpg, .jpeg, .png, .webp) are allowed")

    upload_dir = STUDIO_ROOT / "shared_assets" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    unique_id = str(uuid.uuid4())
    filename = f"{unique_id}{ext}"
    file_path = upload_dir / filename

    contents = await file.read()
    file_path.write_bytes(contents)

    AssetFactory().create_asset(
        project_id="LIBRARY",
        asset_id=f"UPLOAD_{unique_id}",
        kind=AssetKind.UPLOADED.value,
        name=file.filename or filename,
        file_path=str(file_path),
    )

    return {
        "filename": filename,
        "original_name": file.filename or filename,
        "path": str(file_path).replace("\\", "/"),
        "size_bytes": len(contents),
        "stream_url": "/api/v1/media/stream?" + urlencode({"path": str(file_path)})
    }


@router.get("/images")
def list_images():
    """List ALL available images from uploads and generated renders."""
    images = []

    # 1. shared_assets/uploads/
    upload_dir = STUDIO_ROOT / "shared_assets" / "uploads"
    if upload_dir.exists():
        for img in upload_dir.glob("*.*"):
            if img.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                stat = img.stat()
                images.append({
                    "name": img.name,
                    "source": "upload",
                    "path": str(img).replace("\\", "/"),
                    "stream_url": "/api/v1/media/stream?" + urlencode({"path": str(img)}),
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created_time": stat.st_mtime,
                })

    # 2. projects/*/renders/creator_mode/*/
    projects_dir = STUDIO_ROOT / "projects"
    if projects_dir.exists():
        for proj in projects_dir.iterdir():
            if proj.is_dir():
                creator_dir = proj / "renders" / "creator_mode"
                if creator_dir.exists():
                    for run_dir in creator_dir.iterdir():
                        if run_dir.is_dir():
                            for img in list(run_dir.glob("*.png")) + list(run_dir.glob("*.jpg")) + list(run_dir.glob("*.jpeg")):
                                if img.name.startswith("shot_") or img.name.startswith("keyframe_"):
                                    stat = img.stat()
                                    images.append({
                                        "name": img.name,
                                        "source": "generated",
                                        "path": str(img).replace("\\", "/"),
                                        "stream_url": "/api/v1/media/stream?" + urlencode({"path": str(img)}),
                                        "size_mb": round(stat.st_size / (1024 * 1024), 2),
                                        "created_time": stat.st_mtime,
                                    })

    # 3. projects/*/assets/edits/ (Qwen editor results)
    if projects_dir.exists():
        for img in projects_dir.glob("*/assets/edits/*.png"):
            stat = img.stat()
            images.append({
                "name": img.name,
                "source": "edited",
                "path": str(img).replace("\\", "/"),
                "stream_url": "/api/v1/media/stream?" + urlencode({"path": str(img)}),
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_time": stat.st_mtime,
            })

    conn = get_connection()
    try:
        asset_ids_by_path = {
            row["file_path"]: row["id"] for row in conn.execute("SELECT id, file_path FROM assets")
        }
    finally:
        conn.close()
    for img in images:
        img["asset_id"] = asset_ids_by_path.get(img["path"].replace("/", "\\")) or asset_ids_by_path.get(img["path"])

    images.sort(key=lambda x: x["created_time"], reverse=True)
    return {"images": images}


@router.delete("/image")
def delete_image(req: DeleteImageRequest):
    """Deletes an image from the uploads directory."""
    file_path = Path(req.path)
    if not file_path.is_absolute():
        file_path = STUDIO_ROOT / file_path

    file_path = file_path.resolve()
    upload_dir = (STUDIO_ROOT / "shared_assets" / "uploads").resolve()

    if not file_path.is_relative_to(upload_dir):
        raise HTTPException(status_code=403, detail="Can only delete images from shared_assets/uploads")

    if file_path.exists() and file_path.is_file():
        file_path.unlink()
        conn = get_connection()
        try:
            conn.execute("DELETE FROM assets WHERE file_path = ?", (str(file_path),))
            conn.commit()
        finally:
            conn.close()
        return {"deleted": True}
    raise HTTPException(status_code=404, detail="Image not found")
