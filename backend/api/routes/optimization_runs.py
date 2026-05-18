"""优化运行路由模块，提供优化任务的创建、查询、报告获取与取消接口。"""

import json

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select

from backend.api.dependencies import DbSession, get_db
from backend.core.exceptions import not_found
from backend.models.artifact import Artifact
from backend.models.optimization_run import OptimizationRun
from backend.schemas.optimization import (
    OptimizationCancelResponse,
    OptimizationReportResponse,
    OptimizationRunCreateRequest,
    OptimizationRunListResponse,
    OptimizationRunResponse,
)
from backend.services.artifact_service import load_artifact_content
from backend.services.job_service import list_jobs, request_cancel_job
from backend.services.optimization_service import create_optimization_run_and_job

router = APIRouter(prefix="/api/v1/optimization-runs", tags=["optimization-runs"])


@router.post("", response_model=OptimizationRunResponse, status_code=status.HTTP_201_CREATED)
def create_optimization_run(
    payload: OptimizationRunCreateRequest,
    db: DbSession = Depends(get_db),
) -> OptimizationRun:
    """创建优化运行及其关联的后台作业。

    Args:
        payload: 优化运行创建请求数据。
        db: 数据库会话。

    Returns:
        新创建的优化运行对象。
    """
    return create_optimization_run_and_job(
        db=db,
        project_id=payload.project_id,
        dataset_id=payload.dataset_id,
        prompt_id=payload.prompt_id,
        optimizer_name=payload.optimizer_name,
        optimizer_config_snapshot_json=payload.optimizer_config_snapshot_json,
    )


@router.get("", response_model=OptimizationRunListResponse)
def list_optimization_runs(
    project_id: int | None = Query(default=None),
    db: DbSession = Depends(get_db),
) -> OptimizationRunListResponse:
    """获取优化运行列表，支持按项目 ID 筛选。

    Args:
        project_id: 可选的项目 ID 筛选条件。
        db: 数据库会话。

    Returns:
        包含优化运行列表和总数的响应。
    """
    query = select(OptimizationRun).order_by(OptimizationRun.created_at.desc())
    if project_id is not None:
        query = query.where(OptimizationRun.project_id == project_id)
    items = list(db.scalars(query))
    return OptimizationRunListResponse(items=items, total=len(items))


@router.get("/{run_id}", response_model=OptimizationRunResponse)
def get_optimization_run(run_id: int, db: DbSession = Depends(get_db)) -> OptimizationRun:
    """获取指定优化运行详情。

    Args:
        run_id: 优化运行 ID。
        db: 数据库会话。

    Returns:
        优化运行对象。
    """
    run = db.get(OptimizationRun, run_id)
    if run is None:
        raise not_found(f"Optimization run {run_id} not found")
    return run


@router.get("/{run_id}/report", response_model=OptimizationReportResponse)
def get_optimization_report(
    run_id: int, db: DbSession = Depends(get_db)
) -> OptimizationReportResponse:
    """获取优化运行报告。

    Args:
        run_id: 优化运行 ID。
        db: 数据库会话。

    Returns:
        包含优化报告详情的响应。
    """
    run = db.get(OptimizationRun, run_id)
    if run is None:
        raise not_found(f"Optimization run {run_id} not found")
    artifact = db.scalar(
        select(Artifact).where(
            Artifact.owner_type == "optimization_run",
            Artifact.owner_id == run_id,
            Artifact.artifact_type == "report",
        )
    )
    if artifact is None:
        raise not_found(f"Report for optimization run {run_id} not found")
    loaded = load_artifact_content(db, artifact.id)
    return OptimizationReportResponse(**json.loads(loaded["content"]))


@router.post("/{run_id}/cancel", response_model=OptimizationCancelResponse)
def cancel_optimization_run(
    run_id: int, db: DbSession = Depends(get_db)
) -> OptimizationCancelResponse:
    """请求取消指定优化运行。

    Args:
        run_id: 优化运行 ID。
        db: 数据库会话。

    Returns:
        包含优化运行 ID 和更新后状态的响应。
    """
    run = db.get(OptimizationRun, run_id)
    if run is None:
        raise not_found(f"Optimization run {run_id} not found")
    jobs = list_jobs(db)
    related_job = next(
        (job for job in jobs if job.target_type == "optimization_run" and job.target_id == run_id),
        None,
    )
    if related_job is not None:
        request_cancel_job(db, related_job.id)
    run.status = "cancel_requested" if run.status == "running" else "cancelled"
    db.add(run)
    db.commit()
    db.refresh(run)
    return OptimizationCancelResponse(id=run.id, status=run.status)
