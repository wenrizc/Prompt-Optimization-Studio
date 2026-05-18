"""优化运行（Optimization Run）相关的请求与响应模式。

定义优化任务的创建、报告查询与取消等 API 模式。
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.schemas.common import ORMModel


class OptimizationRunCreateRequest(BaseModel):
    """创建优化运行任务的请求模式。"""
    project_id: int
    dataset_id: int
    prompt_id: int
    optimizer_name: Literal["bootstrap_fewshot", "miprov2", "gepa"]
    optimizer_config_snapshot_json: dict[str, Any] = Field(default_factory=dict)


class OptimizationRunResponse(ORMModel):
    """单个优化运行任务的详细响应模式。"""
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
    """优化运行任务分页列表响应模式。"""
    items: list[OptimizationRunResponse]
    total: int


class OptimizationReportResponse(BaseModel):
    """优化报告的详细响应模式，包含摘要、分数分解和回归样例。"""
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
    """取消优化运行任务的响应模式。"""
    id: int
    status: str
