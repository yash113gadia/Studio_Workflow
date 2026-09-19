import uuid
from datetime import datetime, timezone
from typing import Optional, List
from app.core.database import get_connection
from app.core.models import ProjectRecord, ProjectCreate, ProjectKind


class ProjectManager:

    @classmethod
    def create_project(cls, p_in: ProjectCreate) -> ProjectRecord:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            p_id = f"proj_{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc).isoformat()

            cursor.execute("""
            INSERT INTO projects (
                id, name, kind, description, style_id, autonomy_mode, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p_id, p_in.name, p_in.kind.value, p_in.description,
                p_in.style_id, p_in.autonomy_mode, now, now
            ))
            conn.commit()
            return cls.get_project(p_id)
        finally:
            conn.close()

    @classmethod
    def get_project(cls, project_id: str) -> Optional[ProjectRecord]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return ProjectRecord(
                id=row["id"],
                name=row["name"],
                kind=ProjectKind(row["kind"]),
                description=row["description"],
                style_id=row["style_id"],
                autonomy_mode=row["autonomy_mode"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )
        finally:
            conn.close()

    @classmethod
    def list_projects(cls) -> List[ProjectRecord]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            return [
                ProjectRecord(
                    id=row["id"],
                    name=row["name"],
                    kind=ProjectKind(row["kind"]),
                    description=row["description"],
                    style_id=row["style_id"],
                    autonomy_mode=row["autonomy_mode"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"]
                ) for row in rows
            ]
        finally:
            conn.close()
