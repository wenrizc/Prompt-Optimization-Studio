"""后台作业调度服务。

提供作业的创建、领取、进度更新、完成和取消等功能。
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.exceptions import not_found
from backend.models.job import Job
from backend.models.run_log import RunLog

LOCK_TTL_SECONDS = 300


def create_job(
    db: Session,
    job_type: str,
    target_type: str,
    target_id: int,
    payload_json: dict,
    idempotency_key: str | None = None,
    max_retries: int = 3,
) -> Job:
    """创建后台作业, 支持幂等性键去重。

    Args:
        db: 数据库会话。
        job_type: 作业类型, 如 evaluation 或 optimization。
        target_type: 目标实体类型。
        target_id: 目标实体主键。
        payload_json: 作业负载。
        idempotency_key: 幂等性键, 若重复则返回已有作业。
        max_retries: 最大重试次数。

    Returns:
        创建或已有的 Job 记录。
    """
    key = idempotency_key or f"{job_type}:{target_type}:{target_id}:{uuid4().hex}"
    existing = db.scalar(select(Job).where(Job.idempotency_key == key))
    if existing is not None:
        return existing

    job = Job(
        job_type=job_type,
        target_type=target_type,
        target_id=target_id,
        payload_json=payload_json,
        status="queued",
        progress=0,
        max_retries=max_retries,
        idempotency_key=key,
    )
    db.add(job)
    db.flush()
    return job


def claim_next_job(db: Session, worker_id: str) -> Job | None:
    """从队列中领取下一个待执行的作业。使用乐观锁避免并发重复领取。"""
    from sqlalchemy import update

    now = utcnow()
    # 先查出候选 job id
    job_id = db.scalar(
        select(Job.id).where(Job.status == "queued").order_by(Job.created_at.asc()).limit(1)
    )
    if job_id is None:
        return None

    # 原子 UPDATE：只有 status 仍为 queued 时才成功（乐观锁）
    result = db.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == "queued")
        .values(
            status="running",
            locked_by=worker_id,
            locked_until=now + timedelta(seconds=LOCK_TTL_SECONDS),
            heartbeat_at=now,
            started_at=now,
        )
    )
    db.flush()
    if result.rowcount == 0:
        # 被其他 worker 抢先领取
        return None

    return db.get(Job, job_id)


def update_job_progress(db: Session, job: Job, progress: int, message: str | None = None) -> None:
    """更新作业进度并续约锁。"""
    job.progress = progress
    job.heartbeat_at = utcnow()
    job.locked_until = utcnow() + timedelta(seconds=LOCK_TTL_SECONDS)
    db.add(job)
    if message:
        add_run_log(db, "job", job.id, "info", message)
    db.flush()


def complete_job(db: Session, job: Job) -> None:
    """将作业标记为完成。若已请求取消则执行取消流程。"""
    if job.status == "cancel_requested":
        cancel_job_after_claim(db, job)
        return
    job.status = "succeeded"
    job.progress = 100
    job.finished_at = utcnow()
    job.locked_until = None
    db.add(job)
    add_run_log(db, "job", job.id, "info", "Job completed")
    db.flush()


def fail_job(db: Session, job: Job, error_message: str) -> None:
    """将作业标记为失败并记录错误信息。"""
    job.status = "failed"
    job.error_message = error_message
    job.finished_at = utcnow()
    job.locked_until = None
    db.add(job)
    add_run_log(db, "job", job.id, "error", error_message)
    db.flush()


def request_cancel_job(db: Session, job_id: int) -> Job:
    """请求取消作业, 若作业在队列中则直接取消, 否则标记为取消请求。"""
    job = db.get(Job, job_id)
    if job is None:
        raise not_found(f"Job {job_id} not found")
    if job.status == "queued":
        job.status = "cancelled"
        job.finished_at = utcnow()
    elif job.status == "running":
        job.status = "cancel_requested"
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def cancel_job_after_claim(db: Session, job: Job) -> None:
    """在 Worker 安全检查点执行作业取消。"""
    job.status = "cancelled"
    job.finished_at = utcnow()
    job.locked_until = None
    db.add(job)
    add_run_log(db, "job", job.id, "warning", "Job cancelled at a worker safety checkpoint")
    db.flush()


def add_run_log(
    db: Session,
    run_type: str,
    run_id: int,
    level: str,
    message: str,
    data_json: dict | None = None,
) -> RunLog:
    """添加运行日志记录。

    Args:
        db: 数据库会话。
        run_type: 运行类型, 如 job 或 optimization。
        run_id: 关联实体主键。
        level: 日志级别。
        message: 日志消息。
        data_json: 附加数据。

    Returns:
        创建的 RunLog 记录。
    """
    log = RunLog(
        run_type=run_type,
        run_id=run_id,
        level=level,
        message=message,
        data_json=data_json or {},
    )
    db.add(log)
    db.flush()
    return log


def list_jobs(db: Session, status_filter: str | None = None) -> list[Job]:
    """查询作业列表, 可按状态过滤。"""
    query = select(Job).order_by(Job.created_at.desc())
    if status_filter:
        query = query.where(Job.status == status_filter)
    return list(db.scalars(query))


def utcnow() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(UTC)
