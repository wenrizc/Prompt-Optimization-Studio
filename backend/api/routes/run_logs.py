"""运行日志路由模块，提供评估和优化运行日志的查询接口。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from backend.api.dependencies import DbSession, get_db
from backend.models.run_log import RunLog
from backend.schemas.run_log import RunLogListResponse

router = APIRouter(prefix="/api/v1/run-logs", tags=["run-logs"])


@router.get("", response_model=RunLogListResponse)
def list_run_logs(
    run_type: str | None = Query(default=None),
    run_id: int | None = Query(default=None),
    db: DbSession = Depends(get_db),
) -> RunLogListResponse:
    """获取运行日志列表，支持按运行类型和运行 ID 筛选。

    Args:
        run_type: 可选的运行类型筛选条件（evaluation 或 optimization）。
        run_id: 可选的运行 ID 筛选条件。
        db: 数据库会话。

    Returns:
        包含日志条目列表和总数的响应。
    """
    query = select(RunLog).order_by(RunLog.created_at.desc())
    if run_type is not None:
        query = query.where(RunLog.run_type == run_type)
    if run_id is not None:
        query = query.where(RunLog.run_id == run_id)
    items = list(db.scalars(query))
    return RunLogListResponse(items=items, total=len(items))
