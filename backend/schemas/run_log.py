"""运行日志（Run Log）相关的响应模式。

定义评估和优化运行过程中的日志记录查询模式。
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from backend.schemas.common import ORMModel


class RunLogResponse(ORMModel):
    """单条运行日志的详细响应模式。"""
    id: int
    run_type: str
    run_id: int
    level: str
    message: str
    data_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class RunLogListResponse(BaseModel):
    """运行日志分页列表响应模式。"""
    items: list[RunLogResponse]
    total: int
