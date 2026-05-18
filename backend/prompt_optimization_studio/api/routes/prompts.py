from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from prompt_optimization_studio.api.dependencies import DbSession, get_db
from prompt_optimization_studio.core.exceptions import not_found
from prompt_optimization_studio.models.project import Project
from prompt_optimization_studio.models.prompt import Prompt
from prompt_optimization_studio.schemas.prompt import (
    PromptCreate,
    PromptListResponse,
    PromptResponse,
    PromptUpdate,
    PromptValidateRequest,
    PromptValidateResponse,
)
from prompt_optimization_studio.services.validators import (
    ensure_prompt_schema_compatible,
    validate_prompt_template,
)

router = APIRouter(prefix="/api/v1/prompts", tags=["prompts"])


@router.post("/validate", response_model=PromptValidateResponse)
def validate_prompt(payload: PromptValidateRequest) -> PromptValidateResponse:
    variables, warnings = validate_prompt_template(payload.user_template)
    warnings.extend(ensure_prompt_schema_compatible(payload.output_schema_json))
    return PromptValidateResponse(valid=True, variables=variables, warnings=warnings)


@router.post("", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
def create_prompt(payload: PromptCreate, db: DbSession = Depends(get_db)) -> Prompt:
    project = db.get(Project, payload.project_id)
    if project is None:
        raise not_found(f"Project {payload.project_id} not found")

    validate_prompt_template(payload.user_template)
    ensure_prompt_schema_compatible(payload.output_schema_json)

    version_query = select(func.max(Prompt.version)).where(
        Prompt.project_id == payload.project_id,
        Prompt.name == payload.name,
    )
    latest_version = db.scalar(version_query) or 0
    prompt = Prompt(**payload.model_dump(), version=latest_version + 1)
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


@router.get("", response_model=PromptListResponse)
def list_prompts(
    project_id: int | None = Query(default=None),
    db: DbSession = Depends(get_db),
) -> PromptListResponse:
    query = select(Prompt).order_by(Prompt.created_at.desc())
    if project_id is not None:
        query = query.where(Prompt.project_id == project_id)
    items = list(db.scalars(query))
    return PromptListResponse(items=items, total=len(items))


@router.get("/{prompt_id}", response_model=PromptResponse)
def get_prompt(prompt_id: int, db: DbSession = Depends(get_db)) -> Prompt:
    prompt = db.get(Prompt, prompt_id)
    if prompt is None:
        raise not_found(f"Prompt {prompt_id} not found")
    return prompt


@router.post("/{prompt_id}/versions", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
def create_prompt_version(
    prompt_id: int,
    payload: PromptUpdate,
    db: DbSession = Depends(get_db),
) -> Prompt:
    prompt = db.get(Prompt, prompt_id)
    if prompt is None:
        raise not_found(f"Prompt {prompt_id} not found")

    next_values = {
        "project_id": prompt.project_id,
        "name": prompt.name,
        "system_prompt": payload.system_prompt if payload.system_prompt is not None else prompt.system_prompt,
        "user_template": payload.user_template if payload.user_template is not None else prompt.user_template,
        "output_schema_json": payload.output_schema_json if payload.output_schema_json is not None else prompt.output_schema_json,
        "status": payload.status if payload.status is not None else prompt.status,
    }
    validate_prompt_template(next_values["user_template"])
    ensure_prompt_schema_compatible(next_values["output_schema_json"])

    latest_version = db.scalar(
        select(func.max(Prompt.version)).where(
            Prompt.project_id == prompt.project_id,
            Prompt.name == prompt.name,
        )
    ) or prompt.version
    new_prompt = Prompt(**next_values, version=latest_version + 1)
    db.add(new_prompt)
    db.commit()
    db.refresh(new_prompt)
    return new_prompt
