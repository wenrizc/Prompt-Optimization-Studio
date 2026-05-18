from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from prompt_optimization_studio.schemas.common import ORMModel


class OptimizationRunCreateRequest(BaseModel):
    project_id: int
    dataset_id: int
    prompt_id: int
    optimizer_name: Literal["bootstrap_fewshot", "miprov2", "gepa"]
    metric_config_snapshot_json: dict[str, Any] = Field(
        default_factory=lambda: {"metric": "json_field_accuracy"}
    )
    model_config_snapshot_json: dict[str, Any] = Field(
        default_factory=lambda: {"provider": "mock", "model": "mock"}
    )
    optimizer_config_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    random_seed: int = 42


class OptimizationRunResponse(ORMModel):
    id: int
    project_id: int
    dataset_id: int
    prompt_id: int
    optimizer_name: str
    status: str
    progress: int
    baseline_score: float | None
    optimized_score: float | None
    error_message: str | None
    artifact_dir: str | None
    prompt_snapshot_json: dict[str, Any]
    dataset_split_snapshot_json: dict[str, Any]
    model_config_snapshot_json: dict[str, Any]
    optimizer_config_snapshot_json: dict[str, Any]
    metric_config_snapshot_json: dict[str, Any]
    package_versions_json: dict[str, Any]
    random_seed: int | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OptimizationRunListResponse(BaseModel):
    items: list[OptimizationRunResponse]
    total: int


class OptimizationReportResponse(BaseModel):
    summary: dict[str, Any]
    executive_summary: str | None = None
    results: list[dict[str, Any]]
    warnings: list[str]
    dataset: dict[str, Any] | None = None
    metric: dict[str, Any] | None = None
    optimizer: dict[str, Any] | None = None
    score_breakdown: dict[str, Any] | None = None
    failed_examples: list[dict[str, Any]] = Field(default_factory=list)
    regression_examples: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)


class OptimizationCancelResponse(BaseModel):
    id: int
    status: str


class RunComparisonResponse(BaseModel):
    items: list[dict[str, Any]]
