import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from prompt_optimization_studio.core.constants import BUILTIN_TASK_KEYS, PROJECT_STATUSES
from prompt_optimization_studio.schemas.common import ORMModel

TASK_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,49}$")


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    task_kind: Literal["builtin", "custom"]
    task_key: str = Field(min_length=3, max_length=50)
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
        if not TASK_KEY_PATTERN.match(value):
            raise ValueError("task_key must start with a letter and use lowercase letters, numbers, or underscores")
        return value

    @field_validator("input_schema_json", "output_schema_json", "default_metric_config_json", "task_definition_json", "report_profile_json")
    @classmethod
    def validate_json_object(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("must be a JSON object")
        return value

    @model_validator(mode="after")
    def validate_task_kind_match(self) -> "ProjectBase":
        if self.task_kind == "builtin":
            if self.task_key not in BUILTIN_TASK_KEYS:
                raise ValueError(f"builtin task_key must be one of: {', '.join(sorted(BUILTIN_TASK_KEYS))}")
        else:
            if self.task_key in BUILTIN_TASK_KEYS:
                raise ValueError("custom task_key cannot reuse a builtin task name")
        return self


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
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

    @field_validator("input_schema_json", "output_schema_json", "default_metric_config_json", "task_definition_json", "report_profile_json")
    @classmethod
    def validate_optional_json_object(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is not None and not isinstance(value, dict):
            raise ValueError("must be a JSON object")
        return value


class ProjectResponse(ORMModel):
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
    items: list[ProjectResponse]
    total: int
    statuses: list[str] = Field(default_factory=lambda: sorted(PROJECT_STATUSES))
