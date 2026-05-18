"""项目路由模块，提供项目的增删改查、归档和内置任务模板查询接口。"""

from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select

from backend.api.dependencies import DbSession, get_db
from backend.core.constants import PROJECT_STATUSES
from backend.core.exceptions import not_found
from backend.models.project import Project
from backend.schemas.project import (
    BuiltinTaskCatalogResponse,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from backend.services.task_catalog import (
    list_builtin_task_templates,
    resolve_project_create_payload,
)
from backend.services.validators import (
    ensure_task_key_allowed,
    validate_task_contract_alignment,
)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("/builtin-tasks", response_model=BuiltinTaskCatalogResponse)
def list_builtin_tasks(
    locale: Literal["en", "zh"] = Query(default="en"),
) -> BuiltinTaskCatalogResponse:
    """获取内置任务模板目录。

    Args:
        locale: 语言标识，支持 "en" 和 "zh"。

    Returns:
        包含内置任务模板列表的响应。
    """
    return BuiltinTaskCatalogResponse(items=list_builtin_task_templates(locale=locale))


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: DbSession = Depends(get_db)) -> Project:
    """创建新项目。

    Args:
        payload: 项目创建请求数据。
        db: 数据库会话。

    Returns:
        新创建的项目对象。
    """
    ensure_task_key_allowed(payload.task_kind, payload.task_key)
    resolved_payload = resolve_project_create_payload(payload)
    validate_task_contract_alignment(resolved_payload, task_kind=payload.task_kind)
    project = Project(**resolved_payload)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=ProjectListResponse)
def list_projects(
    status_filter: str | None = Query(default=None, alias="status"),
    db: DbSession = Depends(get_db),
) -> ProjectListResponse:
    """获取项目列表，支持按状态筛选。

    Args:
        status_filter: 可选的状态筛选条件。
        db: 数据库会话。

    Returns:
        包含项目列表、总数和可用状态列表的响应。
    """
    query = select(Project).order_by(Project.created_at.desc())
    if status_filter:
        query = query.where(Project.status == status_filter)
    items = list(db.scalars(query))
    return ProjectListResponse(items=items, total=len(items), statuses=sorted(PROJECT_STATUSES))


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: DbSession = Depends(get_db)) -> Project:
    """获取指定项目详情。

    Args:
        project_id: 项目 ID。
        db: 数据库会话。

    Returns:
        项目对象。
    """
    project = db.get(Project, project_id)
    if project is None:
        raise not_found(f"Project {project_id} not found")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int, payload: ProjectUpdate, db: DbSession = Depends(get_db)
) -> Project:
    """更新指定项目属性。

    Args:
        project_id: 项目 ID。
        payload: 项目更新请求数据，仅包含需要更新的字段。
        db: 数据库会话。

    Returns:
        更新后的项目对象。
    """
    project = db.get(Project, project_id)
    if project is None:
        raise not_found(f"Project {project_id} not found")

    next_values = {
        **{
            "task_key": project.task_key,
            "input_schema_json": project.input_schema_json,
            "output_schema_json": project.output_schema_json,
            "default_metric_config_json": project.default_metric_config_json,
            "task_definition_json": project.task_definition_json,
            "report_profile_json": project.report_profile_json,
        },
        **payload.model_dump(exclude_unset=True),
    }
    validate_task_contract_alignment(next_values, task_kind=project.task_kind)

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, key, value)

    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.post("/{project_id}/archive", response_model=ProjectResponse)
def archive_project(project_id: int, db: DbSession = Depends(get_db)) -> Project:
    """归档指定项目，将状态设置为 archived。

    Args:
        project_id: 项目 ID。
        db: 数据库会话。

    Returns:
        归档后的项目对象。
    """
    project = db.get(Project, project_id)
    if project is None:
        raise not_found(f"Project {project_id} not found")
    project.status = "archived"
    db.add(project)
    db.commit()
    db.refresh(project)
    return project
