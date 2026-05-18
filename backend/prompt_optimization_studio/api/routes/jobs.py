from fastapi import APIRouter, Depends, Query

from prompt_optimization_studio.api.dependencies import DbSession, get_db
from prompt_optimization_studio.schemas.job import JobCancelResponse, JobListResponse, JobResponse
from prompt_optimization_studio.services.job_service import list_jobs, request_cancel_job

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
def get_jobs(
    status_filter: str | None = Query(default=None, alias="status"),
    db: DbSession = Depends(get_db),
) -> JobListResponse:
    items = list_jobs(db, status_filter=status_filter)
    return JobListResponse(items=items, total=len(items))


@router.post("/{job_id}/cancel", response_model=JobCancelResponse)
def cancel_job(job_id: int, db: DbSession = Depends(get_db)) -> JobCancelResponse:
    job = request_cancel_job(db, job_id)
    return JobCancelResponse(id=job.id, status=job.status)
