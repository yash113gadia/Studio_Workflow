from typing import List
from fastapi import APIRouter, HTTPException
from app.core.projects import ProjectManager
from app.core.models import ProjectRecord, ProjectCreate

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("", response_model=ProjectRecord)
def create_project(project_in: ProjectCreate):
    return ProjectManager.create_project(project_in)


@router.get("", response_model=List[ProjectRecord])
def list_projects():
    return ProjectManager.list_projects()


@router.get("/{project_id}", response_model=ProjectRecord)
def get_project(project_id: str):
    proj = ProjectManager.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj
