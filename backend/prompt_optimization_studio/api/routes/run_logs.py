from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from prompt_optimization_studio.api.dependencies import DbSession, get_db
from prompt_optimization_studio.models.run_log import RunLog
from prompt_optimization_studio.schemas.run_log import RunLogListResponse

router = APIRouter(prefix="/api/v1/run-logs", tags=["run-logs"])


@router.get("", response_model=RunLogListResponse)
def list_run_logs(
    run_type: str | None = Query(default=None),
    run_id: int | None = Query(default=None),
    db: DbSession = Depends(get_db),
) -> RunLogListResponse:
    query = select(RunLog).order_by(RunLog.created_at.desc())
    if run_type is not None:
        query = query.where(RunLog.run_type == run_type)
    if run_id is not None:
        query = query.where(RunLog.run_id == run_id)
    items = list(db.scalars(query))
    return RunLogListResponse(items=items, total=len(items))
