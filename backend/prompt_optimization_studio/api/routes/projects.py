from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select

from prompt_optimization_studio.api.dependencies import DbSession, get_db
from prompt_optimization_studio.core.constants import PROJECT_STATUSES
from prompt_optimization_studio.core.exceptions import not_found
from prompt_optimization_studio.models.project import Project
from prompt_optimization_studio.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from prompt_optimization_studio.services.validators import ensure_task_key_allowed

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: DbSession = Depends(get_db)) -> Project:
    ensure_task_key_allowed(payload.task_kind, payload.task_key)
    project = Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=ProjectListResponse)
def list_projects(
    status_filter: str | None = Query(default=None, alias="status"),
    db: DbSession = Depends(get_db),
) -> ProjectListResponse:
    query = select(Project).order_by(Project.created_at.desc())
    if status_filter:
        query = query.where(Project.status == status_filter)
    items = list(db.scalars(query))
    return ProjectListResponse(items=items, total=len(items), statuses=sorted(PROJECT_STATUSES))


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: DbSession = Depends(get_db)) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise not_found(f"Project {project_id} not found")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, payload: ProjectUpdate, db: DbSession = Depends(get_db)) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise not_found(f"Project {project_id} not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, key, value)

    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.post("/{project_id}/archive", response_model=ProjectResponse)
def archive_project(project_id: int, db: DbSession = Depends(get_db)) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise not_found(f"Project {project_id} not found")
    project.status = "archived"
    db.add(project)
    db.commit()
    db.refresh(project)
    return project
