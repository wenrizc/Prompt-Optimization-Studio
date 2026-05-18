import json

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select

from prompt_optimization_studio.api.dependencies import DbSession, get_db
from prompt_optimization_studio.core.exceptions import not_found
from prompt_optimization_studio.models.artifact import Artifact
from prompt_optimization_studio.models.optimization_run import OptimizationRun
from prompt_optimization_studio.schemas.optimization import (
    OptimizationCancelResponse,
    OptimizationReportResponse,
    OptimizationRunCreateRequest,
    OptimizationRunListResponse,
    OptimizationRunResponse,
    RunComparisonResponse,
)
from prompt_optimization_studio.services.artifact_service import load_artifact_content
from prompt_optimization_studio.services.job_service import list_jobs, request_cancel_job
from prompt_optimization_studio.services.optimization_service import create_optimization_run_and_job

router = APIRouter(prefix="/api/v1/optimization-runs", tags=["optimization-runs"])


@router.post("", response_model=OptimizationRunResponse, status_code=status.HTTP_201_CREATED)
def create_optimization_run(
    payload: OptimizationRunCreateRequest,
    db: DbSession = Depends(get_db),
) -> OptimizationRun:
    return create_optimization_run_and_job(
        db=db,
        project_id=payload.project_id,
        dataset_id=payload.dataset_id,
        prompt_id=payload.prompt_id,
        optimizer_name=payload.optimizer_name,
        metric_config_snapshot_json=payload.metric_config_snapshot_json,
        model_config_snapshot_json=payload.model_config_snapshot_json,
        optimizer_config_snapshot_json=payload.optimizer_config_snapshot_json,
        random_seed=payload.random_seed,
    )


@router.get("", response_model=OptimizationRunListResponse)
def list_optimization_runs(
    project_id: int | None = Query(default=None),
    db: DbSession = Depends(get_db),
) -> OptimizationRunListResponse:
    query = select(OptimizationRun).order_by(OptimizationRun.created_at.desc())
    if project_id is not None:
        query = query.where(OptimizationRun.project_id == project_id)
    items = list(db.scalars(query))
    return OptimizationRunListResponse(items=items, total=len(items))


@router.get("/{run_id}", response_model=OptimizationRunResponse)
def get_optimization_run(run_id: int, db: DbSession = Depends(get_db)) -> OptimizationRun:
    run = db.get(OptimizationRun, run_id)
    if run is None:
        raise not_found(f"Optimization run {run_id} not found")
    return run


@router.get("/{run_id}/report", response_model=OptimizationReportResponse)
def get_optimization_report(run_id: int, db: DbSession = Depends(get_db)) -> OptimizationReportResponse:
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
def cancel_optimization_run(run_id: int, db: DbSession = Depends(get_db)) -> OptimizationCancelResponse:
    run = db.get(OptimizationRun, run_id)
    if run is None:
        raise not_found(f"Optimization run {run_id} not found")
    jobs = list_jobs(db)
    related_job = next((job for job in jobs if job.target_type == "optimization_run" and job.target_id == run_id), None)
    if related_job is not None:
        request_cancel_job(db, related_job.id)
    run.status = "cancel_requested" if run.status == "running" else "cancelled"
    db.add(run)
    db.commit()
    db.refresh(run)
    return OptimizationCancelResponse(id=run.id, status=run.status)


@router.get("/compare/runs", response_model=RunComparisonResponse)
def compare_runs(run_ids: str = Query(...), db: DbSession = Depends(get_db)) -> RunComparisonResponse:
    parsed_ids = [int(item.strip()) for item in run_ids.split(",") if item.strip()]
    items = []
    for run_id in parsed_ids:
        run = db.get(OptimizationRun, run_id)
        if run is None:
            continue
        items.append(
            {
                "id": run.id,
                "optimizer_name": run.optimizer_name,
                "status": run.status,
                "baseline_score": run.baseline_score,
                "optimized_score": run.optimized_score,
                "delta": None
                if run.baseline_score is None or run.optimized_score is None
                else run.optimized_score - run.baseline_score,
            }
        )
    return RunComparisonResponse(items=items)
