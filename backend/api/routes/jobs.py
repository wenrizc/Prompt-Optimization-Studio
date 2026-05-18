"""任务管理路由模块，提供任务列表查询和取消接口。"""

from fastapi import APIRouter, Depends, Query

from backend.api.dependencies import DbSession, get_db
from backend.schemas.job import JobCancelResponse, JobListResponse
from backend.services.job_service import list_jobs, request_cancel_job

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
def get_jobs(
    status_filter: str | None = Query(default=None, alias="status"),
    db: DbSession = Depends(get_db),
) -> JobListResponse:
    """获取任务列表，支持按状态筛选。

    Args:
        status_filter: 可选的状态筛选条件。
        db: 数据库会话。

    Returns:
        包含任务列表和总数的响应。
    """
    items = list_jobs(db, status_filter=status_filter)
    return JobListResponse(items=items, total=len(items))


@router.post("/{job_id}/cancel", response_model=JobCancelResponse)
def cancel_job(job_id: int, db: DbSession = Depends(get_db)) -> JobCancelResponse:
    """请求取消指定任务。

    Args:
        job_id: 任务 ID。
        db: 数据库会话。

    Returns:
        包含任务 ID 和更新后状态的响应。
    """
    job = request_cancel_job(db, job_id)
    return JobCancelResponse(id=job.id, status=job.status)
