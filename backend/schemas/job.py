"""异步任务（Job）相关的请求与响应模式。

定义任务详情查询、任务列表及取消等 API 模式。
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from backend.schemas.common import ORMModel


class JobResponse(ORMModel):
    """单个异步任务的详细响应模式。"""
    id: int
    job_type: str
    target_type: str
    target_id: int
    payload_json: dict[str, Any]
    status: str
    progress: int
    error_message: str | None
    locked_by: str | None
    locked_until: datetime | None
    heartbeat_at: datetime | None
    retry_count: int
    max_retries: int
    idempotency_key: str
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    """异步任务分页列表响应模式。"""
    items: list[JobResponse]
    total: int


class JobCancelResponse(BaseModel):
    """取消异步任务的响应模式。"""
    id: int
    status: str
