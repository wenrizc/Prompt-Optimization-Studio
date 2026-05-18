import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from prompt_optimization_studio.schemas.common import ORMModel

TEXT_PLACEHOLDER_PATTERN = re.compile(r"\{text\}")
TEMPLATE_VAR_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


class PromptBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    system_prompt: str = ""
    user_template: str = Field(min_length=1)
    output_schema_json: dict[str, Any] = Field(default_factory=dict)
    status: Literal["draft", "active", "archived"] = "draft"

    @field_validator("output_schema_json")
    @classmethod
    def validate_output_schema(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("output_schema_json must be a JSON object")
        return value

    @field_validator("user_template")
    @classmethod
    def validate_template(cls, value: str) -> str:
        if not TEXT_PLACEHOLDER_PATTERN.search(value):
            raise ValueError("user_template must reference {text}")
        variables = set(TEMPLATE_VAR_PATTERN.findall(value))
        unknown_variables = variables - {"text"}
        if unknown_variables:
            joined = ", ".join(sorted(unknown_variables))
            raise ValueError(f"user_template contains unknown variables: {joined}")
        return value


class PromptCreate(PromptBase):
    project_id: int


class PromptUpdate(BaseModel):
    system_prompt: str | None = None
    user_template: str | None = None
    output_schema_json: dict[str, Any] | None = None
    status: Literal["draft", "active", "archived"] | None = None

    @field_validator("output_schema_json")
    @classmethod
    def validate_optional_schema(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is not None and not isinstance(value, dict):
            raise ValueError("output_schema_json must be a JSON object")
        return value


class PromptValidateRequest(BaseModel):
    user_template: str = Field(min_length=1)
    output_schema_json: dict[str, Any] = Field(default_factory=dict)


class PromptValidateResponse(BaseModel):
    valid: bool
    variables: list[str]
    warnings: list[str]


class PromptResponse(ORMModel):
    id: int
    project_id: int
    name: str
    system_prompt: str
    user_template: str
    output_schema_json: dict[str, Any]
    version: int
    status: str
    created_at: datetime
    updated_at: datetime


class PromptListResponse(BaseModel):
    items: list[PromptResponse]
    total: int
