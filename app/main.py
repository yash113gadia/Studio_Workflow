from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import init_db
from app.core.queue import DurableQueue
from app.api.v1.health import router as health_router
from app.api.v1.projects import router as projects_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.gpu import router as gpu_router
from app.api.v1.assets import router as assets_router



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



@app.get("/")
def root():
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
