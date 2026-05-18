"""自定义任务模板路由模块。"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.api.dependencies import DbSession, get_db
from backend.core.exceptions import conflict, not_found
from backend.models.custom_task_template import CustomTaskTemplate
from backend.schemas.custom_task_template import (
    CustomTaskTemplateCreate,
    CustomTaskTemplateListResponse,
    CustomTaskTemplateResponse,
    CustomTaskTemplateUpdate,
)
from backend.schemas.custom_task_template_generation import (
    CustomTaskTemplateDraftBundle,
    CustomTaskTemplateDraftRequest,
)
from backend.services.custom_task_template_generator import (
    generate_custom_task_template_draft_bundle,
)
from backend.services.validators import (
    ensure_task_key_allowed,
    validate_task_contract_alignment,
)

router = APIRouter(prefix="/api/v1/custom-task-templates", tags=["custom-task-templates"])


@router.get("", response_model=CustomTaskTemplateListResponse)
def list_custom_task_templates(db: DbSession = Depends(get_db)) -> CustomTaskTemplateListResponse:
    """获取自定义任务模板列表。"""

    items = list(db.scalars(select(CustomTaskTemplate).order_by(CustomTaskTemplate.updated_at.desc())))
    return CustomTaskTemplateListResponse(items=items, total=len(items))


@router.post("", response_model=CustomTaskTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_custom_task_template(
    payload: CustomTaskTemplateCreate,
    db: DbSession = Depends(get_db),
) -> CustomTaskTemplate:
    """创建自定义任务模板。"""

    ensure_task_key_allowed("custom", payload.task_key)
    validate_task_contract_alignment(payload.model_dump(), task_kind="custom")
    template = CustomTaskTemplate(**payload.model_dump())
    db.add(template)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict(f"custom task template task_key already exists: {payload.task_key}") from exc
    db.refresh(template)
    return template


@router.post("/generate-draft", response_model=CustomTaskTemplateDraftBundle)
def generate_custom_task_template_draft(
    payload: CustomTaskTemplateDraftRequest,
) -> CustomTaskTemplateDraftBundle:
    """根据自然语言描述生成自定义任务模板草稿。"""

    return generate_custom_task_template_draft_bundle(payload.prompt)


@router.get("/{template_id}", response_model=CustomTaskTemplateResponse)
def get_custom_task_template(template_id: int, db: DbSession = Depends(get_db)) -> CustomTaskTemplate:
    """获取指定自定义任务模板。"""

    template = db.get(CustomTaskTemplate, template_id)
    if template is None:
        raise not_found(f"Custom task template {template_id} not found")
    return template


@router.patch("/{template_id}", response_model=CustomTaskTemplateResponse)
def update_custom_task_template(
    template_id: int,
    payload: CustomTaskTemplateUpdate,
    db: DbSession = Depends(get_db),
) -> CustomTaskTemplate:
    """更新指定自定义任务模板。"""

    template = db.get(CustomTaskTemplate, template_id)
    if template is None:
        raise not_found(f"Custom task template {template_id} not found")

    values = payload.model_dump(exclude_unset=True)
    if "task_key" in values:
        ensure_task_key_allowed("custom", values["task_key"])
    validate_task_contract_alignment(
        {
            "task_key": values.get("task_key", template.task_key),
            "input_schema_json": values.get("input_schema_json", template.input_schema_json),
            "output_schema_json": values.get("output_schema_json", template.output_schema_json),
            "default_metric_config_json": values.get(
                "default_metric_config_json",
                template.default_metric_config_json,
            ),
            "task_definition_json": values.get(
                "task_definition_json",
                template.task_definition_json,
            ),
            "report_profile_json": values.get(
                "report_profile_json",
                template.report_profile_json,
            ),
        },
        task_kind="custom",
    )
    for key, value in values.items():
        setattr(template, key, value)

    db.add(template)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict(
            f"custom task template task_key already exists: {values.get('task_key', template.task_key)}"
        ) from exc
    db.refresh(template)
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_custom_task_template(template_id: int, db: DbSession = Depends(get_db)) -> Response:
    """删除指定自定义任务模板。"""

    template = db.get(CustomTaskTemplate, template_id)
    if template is None:
        raise not_found(f"Custom task template {template_id} not found")
    db.delete(template)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
