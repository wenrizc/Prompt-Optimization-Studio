"""提示词（Prompt）相关的请求与响应模式。

定义提示词的创建、更新、校验、查询及列表等 API 模式。
"""

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.schemas.common import ORMModel

TEMPLATE_VAR_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


class PromptBase(BaseModel):
    """提示词基础模式，包含名称、系统提示和用户模板。"""

    name: str = Field(min_length=1, max_length=255)
    system_prompt: str = ""
    user_template: str = Field(min_length=1)


class PromptCreate(PromptBase):
    """创建提示词的请求模式。"""

    project_id: int


class PromptUpdate(BaseModel):
    """更新提示词的请求模式，所有字段可选。"""

    system_prompt: str | None = None
    user_template: str | None = None


class PromptValidateRequest(BaseModel):
    """提示词模板校验的请求模式。"""

    user_template: str = Field(min_length=1)
    input_schema_json: dict[str, Any] = Field(default_factory=dict)
    output_schema_json: dict[str, Any] = Field(default_factory=dict)


class PromptValidateResponse(BaseModel):
    """提示词模板校验的响应模式，包含变量列表和告警。"""

    valid: bool
    variables: list[str]
    warnings: list[str]


class PromptResponse(ORMModel):
    """单个提示词的详细响应模式。"""

    id: int
    project_id: int
    name: str
    system_prompt: str
    user_template: str
    output_schema_json: dict[str, Any]
    version: int
    created_at: datetime
    updated_at: datetime


class PromptListResponse(BaseModel):
    """提示词分页列表响应模式。"""

    items: list[PromptResponse]
    total: int
