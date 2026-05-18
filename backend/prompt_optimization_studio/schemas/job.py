from datetime import datetime
from typing import Any

from pydantic import BaseModel

from prompt_optimization_studio.schemas.common import ORMModel


class JobResponse(ORMModel):
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
    items: list[JobResponse]
    total: int


class JobCancelResponse(BaseModel):
    id: int
    status: str
