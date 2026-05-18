"""提示词路由模块，提供提示词的创建、查询、版本管理和模板验证接口。"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from backend.api.dependencies import DbSession, get_db
from backend.core.exceptions import not_found
from backend.models.project import Project
from backend.models.prompt import Prompt
from backend.schemas.prompt import (
    PromptCreate,
    PromptListResponse,
    PromptResponse,
    PromptUpdate,
    PromptValidateRequest,
    PromptValidateResponse,
)
from backend.services.validators import (
    ensure_prompt_schema_compatible,
    validate_prompt_template,
)

router = APIRouter(prefix="/api/v1/prompts", tags=["prompts"])


@router.post("/validate", response_model=PromptValidateResponse)
def validate_prompt(payload: PromptValidateRequest) -> PromptValidateResponse:
    """验证提示词模板语法并提取变量。

    Args:
        payload: 提示词验证请求数据。

    Returns:
        包含验证结果、提取变量和警告信息的响应。
    """
    variables, warnings = validate_prompt_template(
        payload.user_template,
        payload.input_schema_json,
    )
    warnings.extend(ensure_prompt_schema_compatible(payload.output_schema_json))
    return PromptValidateResponse(valid=True, variables=variables, warnings=warnings)


@router.post("", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
def create_prompt(payload: PromptCreate, db: DbSession = Depends(get_db)) -> Prompt:
    """创建新提示词，自动分配版本号。

    Args:
        payload: 提示词创建请求数据。
        db: 数据库会话。

    Returns:
        新创建的提示词对象。
    """
    project = db.get(Project, payload.project_id)
    if project is None:
        raise not_found(f"Project {payload.project_id} not found")

    validate_prompt_template(payload.user_template, project.input_schema_json)
    ensure_prompt_schema_compatible(project.output_schema_json)

    version_query = select(func.max(Prompt.version)).where(
        Prompt.project_id == payload.project_id,
        Prompt.name == payload.name,
    )
    latest_version = db.scalar(version_query) or 0
    prompt = Prompt(
        **payload.model_dump(),
        output_schema_json=project.output_schema_json,
        version=latest_version + 1,
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


@router.get("", response_model=PromptListResponse)
def list_prompts(
    project_id: int | None = Query(default=None),
    db: DbSession = Depends(get_db),
) -> PromptListResponse:
    """获取提示词列表，支持按项目 ID 筛选。

    Args:
        project_id: 可选的项目 ID 筛选条件。
        db: 数据库会话。

    Returns:
        包含提示词列表和总数的响应。
    """
    query = select(Prompt).order_by(Prompt.created_at.desc())
    if project_id is not None:
        query = query.where(Prompt.project_id == project_id)
    items = list(db.scalars(query))
    return PromptListResponse(items=items, total=len(items))


@router.get("/{prompt_id}", response_model=PromptResponse)
def get_prompt(prompt_id: int, db: DbSession = Depends(get_db)) -> Prompt:
    """获取指定提示词详情。

    Args:
        prompt_id: 提示词 ID。
        db: 数据库会话。

    Returns:
        提示词对象。
    """
    prompt = db.get(Prompt, prompt_id)
    if prompt is None:
        raise not_found(f"Prompt {prompt_id} not found")
    return prompt


@router.post(
    "/{prompt_id}/versions", response_model=PromptResponse, status_code=status.HTTP_201_CREATED
)
def create_prompt_version(
    prompt_id: int,
    payload: PromptUpdate,
    db: DbSession = Depends(get_db),
) -> Prompt:
    """基于已有提示词创建新版本。

    Args:
        prompt_id: 原始提示词 ID。
        payload: 提示词更新请求数据，未指定的字段沿用原版本值。
        db: 数据库会话。

    Returns:
        新版本的提示词对象。
    """
    prompt = db.get(Prompt, prompt_id)
    if prompt is None:
        raise not_found(f"Prompt {prompt_id} not found")

    next_values = {
        "project_id": prompt.project_id,
        "name": prompt.name,
        "system_prompt": payload.system_prompt
        if payload.system_prompt is not None
        else prompt.system_prompt,
        "user_template": payload.user_template
        if payload.user_template is not None
        else prompt.user_template,
        "output_schema_json": prompt.output_schema_json,
    }
    project = db.get(Project, prompt.project_id)
    if project is None:
        raise not_found(f"Project {prompt.project_id} not found")
    validate_prompt_template(next_values["user_template"], project.input_schema_json)
    ensure_prompt_schema_compatible(next_values["output_schema_json"])

    latest_version = (
        db.scalar(
            select(func.max(Prompt.version)).where(
                Prompt.project_id == prompt.project_id,
                Prompt.name == prompt.name,
            )
        )
        or prompt.version
    )
    new_prompt = Prompt(**next_values, version=latest_version + 1)
    db.add(new_prompt)
    db.commit()
    db.refresh(new_prompt)
    return new_prompt
