"""评估（Evaluation）相关的请求与响应模式。

定义评估任务的创建、报告查询、Worker 运行以及取消等 API 模式。
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.schemas.common import ORMModel


class EvaluationCreateRequest(BaseModel):
    """创建评估任务的请求模式。"""
    project_id: int
    dataset_id: int
    prompt_id: int


class EvaluationReportResponse(BaseModel):
    """评估报告的详细响应模式，包含摘要、逐条结果和告警信息。"""
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
    """单个评估任务的详细响应模式。"""
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
    """评估任务分页列表响应模式。"""
    items: list[EvaluationResponse]
    total: int


class WorkerRunRequest(BaseModel):
    """Worker 执行任务的请求模式。"""
    worker_id: str = Field(default="worker-1")
    max_jobs: int = Field(default=1, ge=1, le=100)


class WorkerRunResponse(BaseModel):
    """Worker 执行任务的响应模式，包含处理统计。"""
    worker_id: str
    processed_jobs: int
    completed_job_ids: list[int]


class EvaluationCancelResponse(BaseModel):
    """取消评估任务的响应模式。"""
    id: int
    status: str
