"""项目（Project）相关的请求与响应模式。

定义项目的创建、更新、查询、列表，以及内置任务模板的目录查询等 API 模式。
"""

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.core.constants import BUILTIN_TASK_KEYS, PROJECT_STATUSES
from backend.schemas.common import ORMModel

TASK_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,49}$")


class ProjectBase(BaseModel):
    """项目基础模式，包含项目创建与校验的公共字段。"""
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    task_kind: Literal["builtin", "custom"]
    task_key: str = Field(min_length=2, max_length=50)
    template_locale: Literal["en", "zh"] | None = None
    task_display_name: str | None = Field(default=None, max_length=255)
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

    @field_validator("task_display_name", "description", "task_description")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """去除可选文本字段的首尾空白，空字符串转为 None。"""
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
        """校验字段值是否为合法 JSON 对象。"""
        if not isinstance(value, dict):
            raise ValueError("must be a JSON object")
        return value

    @model_validator(mode="after")
    def validate_task_kind_match(self) -> "ProjectBase":
        """校验 task_kind 与 task_key 的一致性（builtin 或 custom）。"""
        if self.task_kind == "builtin":
            if self.task_key not in BUILTIN_TASK_KEYS:
                raise ValueError(
                    f"builtin task_key must be one of: {', '.join(sorted(BUILTIN_TASK_KEYS))}"
                )
        else:
            if self.task_key in BUILTIN_TASK_KEYS:
                raise ValueError("custom task_key cannot reuse a builtin task name")
            if not self.task_display_name:
                raise ValueError("custom projects require task_display_name")
        return self


class ProjectCreate(ProjectBase):
    """创建项目的请求模式。"""


class ProjectUpdate(BaseModel):
    """更新项目的请求模式，所有字段可选。"""
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    task_display_name: str | None = Field(default=None, min_length=1, max_length=255)
    task_description: str | None = None
    input_schema_json: dict[str, Any] | None = None
    output_schema_json: dict[str, Any] | None = None
    default_metric_config_json: dict[str, Any] | None = None
    task_definition_json: dict[str, Any] | None = None
    report_profile_json: dict[str, Any] | None = None
    status: Literal["active", "archived"] | None = None

    @field_validator(
        "input_schema_json",
        "output_schema_json",
        "default_metric_config_json",
        "task_definition_json",
        "report_profile_json",
    )
    @classmethod
    def validate_optional_json_object(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        """校验可选 JSON 字段在非 None 时是否为合法 JSON 对象。"""
        if value is not None and not isinstance(value, dict):
            raise ValueError("must be a JSON object")
        return value


class ProjectResponse(ORMModel):
    """单个项目的详细响应模式。"""
    id: int
    name: str
    description: str | None
    task_kind: str
    task_key: str
    task_display_name: str
    task_description: str | None
    input_schema_json: dict[str, Any]
    output_schema_json: dict[str, Any]
    default_metric_config_json: dict[str, Any]
    task_definition_json: dict[str, Any]
    report_profile_json: dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    """项目分页列表响应模式。"""
    items: list[ProjectResponse]
    total: int
    statuses: list[str] = Field(default_factory=lambda: sorted(PROJECT_STATUSES))


class BuiltinTaskTemplateResponse(BaseModel):
    """内置任务模板的详细响应模式。"""
    task_key: str
    task_display_name: str
    task_description: str | None
    input_schema_json: dict[str, Any]
    output_schema_json: dict[str, Any]
    default_metric_config_json: dict[str, Any]
    task_definition_json: dict[str, Any]
    report_profile_json: dict[str, Any]


class BuiltinTaskCatalogResponse(BaseModel):
    """内置任务模板目录的响应模式。"""
    items: list[BuiltinTaskTemplateResponse]
