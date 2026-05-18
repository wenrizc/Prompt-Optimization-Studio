"""自定义任务模板草稿生成结构。"""

from typing import Any

from pydantic import BaseModel, Field, model_validator

from backend.schemas.custom_task_template import CustomTaskTemplateCreate
from backend.services.validators import validate_generated_template_alignment


class CustomTaskTemplateDraftRequest(BaseModel):
    """自然语言生成自定义任务模板草稿的请求。"""

    prompt: str = Field(min_length=10, max_length=4000)


class CustomTaskTemplateGuidanceField(BaseModel):
    """单个配置项的说明信息。"""

    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=1000)
    configurable_fields: list[str] = Field(default_factory=list)
    downstream_usage: list[str] = Field(default_factory=list)
    examples: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CustomTaskTemplateDraftGuidance(BaseModel):
    """模板草稿的展示辅助信息。"""

    overview: str = Field(min_length=1, max_length=2000)
    items: dict[str, CustomTaskTemplateGuidanceField] = Field(default_factory=dict)


class CustomTaskTemplateDraftBundle(BaseModel):
    """自定义任务模板草稿与说明。"""

    draft: CustomTaskTemplateCreate
    guidance: CustomTaskTemplateDraftGuidance

    @model_validator(mode="after")
    def validate_cross_field_alignment(self) -> "CustomTaskTemplateDraftBundle":
        """校验生成草稿的跨字段引用关系。"""
        validate_generated_template_alignment(self.draft.model_dump())
        return self
