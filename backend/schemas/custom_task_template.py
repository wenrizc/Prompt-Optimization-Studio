"""自定义任务模板请求与响应模式。"""

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from backend.schemas.common import ORMModel

TASK_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,49}$")


class CustomTaskTemplateBase(BaseModel):
    """自定义任务模板基础模式。"""

    task_key: str = Field(min_length=2, max_length=50)
    task_display_name: str = Field(min_length=1, max_length=255)
    task_description: str | None = None
    input_schema_json: dict[str, Any] = Field(default_factory=dict)
    output_schema_json: dict[str, Any] = Field(default_factory=dict)
    default_metric_config_json: dict[str, Any] = Field(default_factory=dict)
    task_definition_json: dict[str, Any] = Field(default_factory=dict)
    report_profile_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task_key")
    @classmethod
    def validate_task_key(cls, value: str) -> str:
        """校验 task_key 是否符合命名规范。"""
        if not TASK_KEY_PATTERN.match(value):
            raise ValueError(
                "task_key must start with a letter and use lowercase letters, numbers, or underscores"
            )
        return value

    @field_validator("task_display_name", "task_description")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """清理文本字段首尾空白。"""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator(
        "input_schema_json",
        "output_schema_json",
        "default_metric_config_json",
        "task_definition_json",
        "report_profile_json",
    )
    @classmethod
    def validate_json_object(cls, value: dict[str, Any]) -> dict[str, Any]:
        """校验 JSON 配置字段必须为对象。"""
        if not isinstance(value, dict):
            raise ValueError("must be a JSON object")
        return value


class CustomTaskTemplateCreate(CustomTaskTemplateBase):
    """创建自定义任务模板请求。"""


class CustomTaskTemplateUpdate(BaseModel):
    """更新自定义任务模板请求。"""

    task_key: str | None = Field(default=None, min_length=2, max_length=50)
    task_display_name: str | None = Field(default=None, min_length=1, max_length=255)
    task_description: str | None = None
    input_schema_json: dict[str, Any] | None = None
    output_schema_json: dict[str, Any] | None = None
    default_metric_config_json: dict[str, Any] | None = None
    task_definition_json: dict[str, Any] | None = None
    report_profile_json: dict[str, Any] | None = None

    @field_validator("task_key")
    @classmethod
    def validate_optional_task_key(cls, value: str | None) -> str | None:
        """校验可选 task_key 是否符合命名规范。"""
        if value is None:
            return value
        if not TASK_KEY_PATTERN.match(value):
            raise ValueError(
                "task_key must start with a letter and use lowercase letters, numbers, or underscores"
            )
        return value

    @field_validator("task_display_name", "task_description")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """清理文本字段首尾空白。"""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator(
        "input_schema_json",
        "output_schema_json",
        "default_metric_config_json",
        "task_definition_json",
        "report_profile_json",
    )
    @classmethod
    def validate_optional_json_object(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        """校验可选 JSON 配置字段必须为对象。"""
        if value is not None and not isinstance(value, dict):
            raise ValueError("must be a JSON object")
        return value


class CustomTaskTemplateResponse(ORMModel):
    """单个自定义任务模板响应。"""

    id: int
    task_key: str
    task_display_name: str
    task_description: str | None
    input_schema_json: dict[str, Any]
    output_schema_json: dict[str, Any]
    default_metric_config_json: dict[str, Any]
    task_definition_json: dict[str, Any]
    report_profile_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CustomTaskTemplateListResponse(BaseModel):
    """自定义任务模板列表响应。"""

    items: list[CustomTaskTemplateResponse]
    total: int
