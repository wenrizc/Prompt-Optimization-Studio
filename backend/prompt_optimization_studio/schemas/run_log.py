from datetime import datetime
from typing import Any

from pydantic import BaseModel

from prompt_optimization_studio.schemas.common import ORMModel


class RunLogResponse(ORMModel):
    id: int
    run_type: str
    run_id: int
    level: str
    message: str
    data_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class RunLogListResponse(BaseModel):
    items: list[RunLogResponse]
    total: int
