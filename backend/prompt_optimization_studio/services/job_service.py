from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from prompt_optimization_studio.core.exceptions import not_found
from prompt_optimization_studio.models.job import Job
from prompt_optimization_studio.models.run_log import RunLog

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
    now = utcnow()
    job = db.scalar(
        select(Job)
        .where(Job.status == "queued")
        .order_by(Job.created_at.asc())
        .limit(1)
    )
    if job is None:
        return None

    job.status = "running"
    job.locked_by = worker_id
    job.locked_until = now + timedelta(seconds=LOCK_TTL_SECONDS)
    job.heartbeat_at = now
    job.started_at = now
    db.add(job)
    db.flush()
    return job


def update_job_progress(db: Session, job: Job, progress: int, message: str | None = None) -> None:
    job.progress = progress
    job.heartbeat_at = utcnow()
    job.locked_until = utcnow() + timedelta(seconds=LOCK_TTL_SECONDS)
    db.add(job)
    if message:
        add_run_log(db, "job", job.id, "info", message)
    db.flush()


def complete_job(db: Session, job: Job) -> None:
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
    job.status = "failed"
    job.error_message = error_message
    job.finished_at = utcnow()
    job.locked_until = None
    db.add(job)
    add_run_log(db, "job", job.id, "error", error_message)
    db.flush()


def request_cancel_job(db: Session, job_id: int) -> Job:
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
    query = select(Job).order_by(Job.created_at.desc())
    if status_filter:
        query = query.where(Job.status == status_filter)
    return list(db.scalars(query))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
