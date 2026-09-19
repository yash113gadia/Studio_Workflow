import os
from pathlib import Path
from typing import Dict, Any, List
import yaml
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: List[str] = Field(default_factory=lambda: ["http://127.0.0.1:8188", "http://localhost:8188"])


class GPULeaseConfig(BaseModel):
    resource_name: str = "GPU0_HEAVY"
    heartbeat_interval_seconds: int = 5
    lease_timeout_seconds: int = 30


class QueueConfig(BaseModel):
    max_concurrent_heavy_jobs: int = 1
    heartbeat_timeout_seconds: int = 60
    max_attempts: int = 3


class SafetyConfig(BaseModel):
    minimum_free_disk_gb: float = 80.0


class StudioPaths(BaseModel):
    root: str = Field(default_factory=lambda: str(Path(__file__).resolve().parent.parent.parent))
    configs: str = "configs"
    database: str = "database/studio.db"
    models: str = "models"
    workflows: str = "workflows"
    projects: str = "projects"
    shared_assets: str = "shared_assets"
    logs: str = "logs"
    cache: str = "cache"
    temp: str = "temp"

    def absolute(self, rel: str) -> Path:
        p = Path(rel)
        if p.is_absolute():
            return p
        return Path(self.root) / p


class StudioSettings(BaseModel):
    studio_name: str = "Preeti Studio Local AI OS"
    version: str = "0.1.0"
    environment: str = "development"
    paths: StudioPaths = Field(default_factory=StudioPaths)
    server: ServerConfig = Field(default_factory=ServerConfig)
    gpu_lease: GPULeaseConfig = Field(default_factory=GPULeaseConfig)
    queue: QueueConfig = Field(default_factory=QueueConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)


def load_settings(config_path: Path | None = None) -> StudioSettings:
    if config_path is None:
        root = Path(__file__).resolve().parent.parent.parent
        config_path = root / "configs" / "studio.yaml"
    
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return StudioSettings(**data)
    return StudioSettings()


settings = load_settings()
