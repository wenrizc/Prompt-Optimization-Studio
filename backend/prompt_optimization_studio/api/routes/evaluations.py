from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select

from prompt_optimization_studio.api.dependencies import DbSession, get_db
from prompt_optimization_studio.core.exceptions import not_found
from prompt_optimization_studio.models.artifact import Artifact
from prompt_optimization_studio.models.evaluation import Evaluation
from prompt_optimization_studio.schemas.evaluation import (
    EvaluationCancelResponse,
    EvaluationCreateRequest,
    EvaluationListResponse,
    EvaluationReportResponse,
    EvaluationResponse,
    WorkerRunRequest,
    WorkerRunResponse,
)
from prompt_optimization_studio.services.artifact_service import load_artifact_content
from prompt_optimization_studio.services.evaluation_service import create_evaluation_and_job
from prompt_optimization_studio.services.job_service import list_jobs, request_cancel_job
from prompt_optimization_studio.workers.worker import LocalWorker

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])
worker_router = APIRouter(prefix="/api/v1/worker", tags=["worker"])


@router.post("", response_model=EvaluationResponse, status_code=status.HTTP_201_CREATED)
def create_evaluation(payload: EvaluationCreateRequest, db: DbSession = Depends(get_db)) -> Evaluation:
    return create_evaluation_and_job(
        db=db,
        project_id=payload.project_id,
        dataset_id=payload.dataset_id,
        prompt_id=payload.prompt_id,
        metric_config_json=payload.metric_config_json,
        model_config_json=payload.model_config_json,
        random_seed=payload.random_seed,
    )


@router.get("", response_model=EvaluationListResponse)
def list_evaluations(
    project_id: int | None = Query(default=None),
    db: DbSession = Depends(get_db),
) -> EvaluationListResponse:
    query = select(Evaluation).order_by(Evaluation.created_at.desc())
    if project_id is not None:
        query = query.where(Evaluation.project_id == project_id)
    items = list(db.scalars(query))
    return EvaluationListResponse(items=items, total=len(items))


@router.get("/{evaluation_id}", response_model=EvaluationResponse)
def get_evaluation(evaluation_id: int, db: DbSession = Depends(get_db)) -> Evaluation:
    evaluation = db.get(Evaluation, evaluation_id)
    if evaluation is None:
        raise not_found(f"Evaluation {evaluation_id} not found")
    return evaluation


@router.get("/{evaluation_id}/report", response_model=EvaluationReportResponse)
def get_evaluation_report(evaluation_id: int, db: DbSession = Depends(get_db)) -> EvaluationReportResponse:
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
    import json

    payload = json.loads(loaded["content"])
    return EvaluationReportResponse(**payload)


@router.post("/{evaluation_id}/cancel", response_model=EvaluationCancelResponse)
def cancel_evaluation(evaluation_id: int, db: DbSession = Depends(get_db)) -> EvaluationCancelResponse:
    evaluation = db.get(Evaluation, evaluation_id)
    if evaluation is None:
        raise not_found(f"Evaluation {evaluation_id} not found")
    jobs = list_jobs(db)
    related_job = next((job for job in jobs if job.target_type == "evaluation" and job.target_id == evaluation_id), None)
    if related_job is not None:
        request_cancel_job(db, related_job.id)
    evaluation.status = "cancel_requested" if evaluation.status == "running" else "cancelled"
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return EvaluationCancelResponse(id=evaluation.id, status=evaluation.status)


@worker_router.post("/run-once", response_model=WorkerRunResponse)
def run_worker_once(payload: WorkerRunRequest) -> WorkerRunResponse:
    worker = LocalWorker(payload.worker_id)
    completed_job_ids = worker.run_once(payload.max_jobs)
    return WorkerRunResponse(
        worker_id=payload.worker_id,
        processed_jobs=len(completed_job_ids),
        completed_job_ids=completed_job_ids,
    )
