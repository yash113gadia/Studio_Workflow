from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import init_db
from app.core.queue import DurableQueue
from app.api.v1.health import router as health_router
from app.api.v1.projects import router as projects_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.gpu import router as gpu_router
from app.api.v1.assets import router as assets_router
from app.api.v1.editor import router as editor_router
from app.api.v1.continuity import router as continuity_router
from app.api.v1.novel import router as novel_router
from app.api.v1.qa import router as qa_router
from app.api.v1.video import router as video_router
from app.api.v1.motion import router as motion_router
from app.api.v1.audio import router as audio_router
from app.api.v1.post import router as post_router
from app.api.v1.upscaler import router as upscaler_router
from app.api.v1.thumbnails import router as thumbnails_router
from app.api.v1.creator import router as creator_router
from app.api.v1.series import router as series_router
from app.api.v1.sandbox import router as sandbox_router
from app.api.v1.media import router as media_router




@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database and recover any stale running jobs from crash
    init_db()
    recovered = DurableQueue.recover_stale_running_jobs()
    if recovered > 0:
        print(f"[Studio Core] Recovered {recovered} stale jobs on startup.")
    yield
    # Shutdown
    print("[Studio Core] Shutting down cleanly.")


app = FastAPI(
    title=settings.studio_name,
    version=settings.version,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.server.cors_origins + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(gpu_router, prefix="/api/v1")
app.include_router(assets_router, prefix="/api/v1")
app.include_router(editor_router, prefix="/api/v1")
app.include_router(continuity_router, prefix="/api/v1")
app.include_router(novel_router, prefix="/api/v1")
app.include_router(qa_router, prefix="/api/v1")
app.include_router(video_router, prefix="/api/v1")
app.include_router(motion_router, prefix="/api/v1")
app.include_router(audio_router, prefix="/api/v1")
app.include_router(post_router, prefix="/api/v1")
app.include_router(upscaler_router, prefix="/api/v1")
app.include_router(thumbnails_router, prefix="/api/v1")
app.include_router(creator_router, prefix="/api/v1")
app.include_router(series_router, prefix="/api/v1")
app.include_router(sandbox_router, prefix="/api/v1")
app.include_router(media_router, prefix="/api/v1")


@app.get("/", response_class=FileResponse)
@app.get("/studio", response_class=FileResponse)
def studio_ui():
    """Serves the user-friendly creator web UI."""
    index_file = Path(__file__).resolve().parent / "static" / "index.html"
    return FileResponse(str(index_file), media_type="text/html")


@app.get("/api/v1/info")
def root_info():
    return {
        "studio": settings.studio_name,
        "version": settings.version,
        "status": "online",
        "docs_url": "/docs",
        "api_v1": "/api/v1"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.server.host, port=settings.server.port, reload=False)
