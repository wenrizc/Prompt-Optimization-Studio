"""评估路由模块，提供评估任务的创建、查询、报告获取、取消以及 Worker 执行接口。"""

import json

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select

from backend.api.dependencies import DbSession, get_db
from backend.core.exceptions import not_found
from backend.models.artifact import Artifact
from backend.models.evaluation import Evaluation
from backend.schemas.evaluation import (
    EvaluationCancelResponse,
    EvaluationCreateRequest,
    EvaluationListResponse,
    EvaluationReportResponse,
    EvaluationResponse,
    WorkerRunRequest,
    WorkerRunResponse,
)
from backend.services.artifact_service import load_artifact_content
from backend.services.evaluation_service import create_evaluation_and_job
from backend.services.job_service import list_jobs, request_cancel_job
from backend.workers.worker import LocalWorker

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])
worker_router = APIRouter(prefix="/api/v1/worker", tags=["worker"])


@router.post("", response_model=EvaluationResponse, status_code=status.HTTP_201_CREATED)
def create_evaluation(
    payload: EvaluationCreateRequest, db: DbSession = Depends(get_db)
) -> Evaluation:
    """创建评估任务及其关联的后台作业。

    Args:
        payload: 评估创建请求数据。
        db: 数据库会话。

    Returns:
        新创建的评估对象。
    """
    return create_evaluation_and_job(
        db=db,
        project_id=payload.project_id,
        dataset_id=payload.dataset_id,
        prompt_id=payload.prompt_id,
    )


@router.get("", response_model=EvaluationListResponse)
def list_evaluations(
    project_id: int | None = Query(default=None),
    db: DbSession = Depends(get_db),
) -> EvaluationListResponse:
    """获取评估列表，支持按项目 ID 筛选。

    Args:
        project_id: 可选的项目 ID 筛选条件。
        db: 数据库会话。

    Returns:
        包含评估列表和总数的响应。
    """
    query = select(Evaluation).order_by(Evaluation.created_at.desc())
    if project_id is not None:
        query = query.where(Evaluation.project_id == project_id)
    items = list(db.scalars(query))
    return EvaluationListResponse(items=items, total=len(items))


@router.get("/{evaluation_id}", response_model=EvaluationResponse)
def get_evaluation(evaluation_id: int, db: DbSession = Depends(get_db)) -> Evaluation:
    """获取指定评估详情。

    Args:
        evaluation_id: 评估 ID。
        db: 数据库会话。

    Returns:
        评估对象。
    """
    evaluation = db.get(Evaluation, evaluation_id)
    if evaluation is None:
        raise not_found(f"Evaluation {evaluation_id} not found")
    return evaluation


@router.get("/{evaluation_id}/report", response_model=EvaluationReportResponse)
def get_evaluation_report(
    evaluation_id: int, db: DbSession = Depends(get_db)
) -> EvaluationReportResponse:
    """获取评估报告。

    Args:
        evaluation_id: 评估 ID。
        db: 数据库会话。

    Returns:
        包含评估报告详情的响应。
    """
    evaluation = db.get(Evaluation, evaluation_id)
    if evaluation is None:
        raise not_found(f"Evaluation {evaluation_id} not found")

    artifact = db.scalar(
        select(Artifact).where(
            Artifact.owner_type == "evaluation",
            Artifact.owner_id == evaluation_id,
            Artifact.artifact_type == "report",
        )
    )
    if artifact is None:
        raise not_found(f"Report for evaluation {evaluation_id} not found")
    loaded = load_artifact_content(db, artifact.id)
    payload = json.loads(loaded["content"])
    return EvaluationReportResponse(**payload)


@router.post("/{evaluation_id}/cancel", response_model=EvaluationCancelResponse)
def cancel_evaluation(
    evaluation_id: int, db: DbSession = Depends(get_db)
) -> EvaluationCancelResponse:
    """请求取消指定评估任务。

    Args:
        evaluation_id: 评估 ID。
        db: 数据库会话。

    Returns:
        包含评估 ID 和更新后状态的响应。
    """
    evaluation = db.get(Evaluation, evaluation_id)
    if evaluation is None:
        raise not_found(f"Evaluation {evaluation_id} not found")
    jobs = list_jobs(db)
    related_job = next(
        (job for job in jobs if job.target_type == "evaluation" and job.target_id == evaluation_id),
        None,
    )
    if related_job is not None:
        request_cancel_job(db, related_job.id)
    evaluation.status = "cancel_requested" if evaluation.status == "running" else "cancelled"
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return EvaluationCancelResponse(id=evaluation.id, status=evaluation.status)


@worker_router.post("/run-once", response_model=WorkerRunResponse)
def run_worker_once(payload: WorkerRunRequest) -> WorkerRunResponse:
    """触发 Worker 执行一次任务轮询。

    Args:
        payload: Worker 运行请求数据，包含 Worker ID 和最大任务数。

    Returns:
        包含 Worker ID、处理任务数和已完成任务 ID 列表的响应。
    """
    worker = LocalWorker(payload.worker_id)
    completed_job_ids = worker.run_once(payload.max_jobs)
    return WorkerRunResponse(
        worker_id=payload.worker_id,
        processed_jobs=len(completed_job_ids),
        completed_job_ids=completed_job_ids,
    )
