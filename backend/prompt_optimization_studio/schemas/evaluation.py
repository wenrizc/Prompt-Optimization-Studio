from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from prompt_optimization_studio.schemas.common import ORMModel


class EvaluationCreateRequest(BaseModel):
    project_id: int
    dataset_id: int
    prompt_id: int
    metric_config_json: dict[str, Any] = Field(default_factory=lambda: {"metric": "json_field_accuracy"})
    model_config_json: dict[str, Any] = Field(default_factory=lambda: {"provider": "mock", "model": "mock"})
    random_seed: int = 42


class EvaluationReportResponse(BaseModel):
    summary: dict[str, Any]
    executive_summary: str | None = None
    results: list[dict[str, Any]]
    warnings: list[str]
    dataset: dict[str, Any] | None = None
    metric: dict[str, Any] | None = None
    score_breakdown: dict[str, Any] | None = None
    failed_examples: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    program_state: dict[str, Any] | None = None


class EvaluationResponse(ORMModel):
    id: int
    project_id: int
    dataset_id: int
    prompt_id: int
    status: str
    progress: int
    score: float | None
    metric_config_json: dict[str, Any]
    model_config_json: dict[str, Any]
    prompt_snapshot_json: dict[str, Any]
    dataset_split_snapshot_json: dict[str, Any]
    package_versions_json: dict[str, Any]
    random_seed: int | None
    artifact_dir: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EvaluationListResponse(BaseModel):
    items: list[EvaluationResponse]
    total: int


class WorkerRunRequest(BaseModel):
    worker_id: str = Field(default="worker-1")
    max_jobs: int = Field(default=1, ge=1, le=100)


class WorkerRunResponse(BaseModel):
    worker_id: str
    processed_jobs: int
    completed_job_ids: list[int]


class EvaluationCancelResponse(BaseModel):
    id: int
    status: str
