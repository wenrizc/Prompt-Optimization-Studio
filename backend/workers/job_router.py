"""任务路由模块，根据任务类型将作业分发到对应的处理函数。"""

from sqlalchemy.orm import Session

from backend.core.exceptions import bad_request
from backend.models.evaluation import Evaluation
from backend.models.job import Job
from backend.models.optimization_run import OptimizationRun
from backend.services.evaluation_service import (
    execute_evaluation,
    finalize_evaluation_failure,
    finalize_evaluation_success,
)
from backend.services.job_service import (
    cancel_job_after_claim,
    update_job_progress,
)
from backend.services.optimization_service import (
    execute_optimization_run,
    finalize_optimization_failure,
    finalize_optimization_success,
)


def process_job(db: Session, job: Job) -> None:
    """根据任务类型路由到对应的处理函数。

    Args:
        db: 数据库会话。
        job: 待处理的任务对象。

    Raises:
        BadRequest: 当任务类型不被支持时抛出。
    """
    if job.job_type == "evaluation":
        process_evaluation_job(db, job)
        return
    if job.job_type == "optimization":
        process_optimization_job(db, job)
        return
    raise bad_request(f"unsupported job_type: {job.job_type}")


def process_evaluation_job(db: Session, job: Job) -> None:
    """处理评估类型任务，执行评估流程并更新状态。

    Args:
        db: 数据库会话。
        job: 待处理的评估任务对象。
    """
    if job.status == "cancel_requested":
        cancel_job_after_claim(db, job)
        return
    evaluation = db.get(Evaluation, job.target_id)
    if evaluation is None:
        raise bad_request(f"evaluation {job.target_id} not found")

    evaluation.status = "running"
    evaluation.progress = 5
    db.add(evaluation)
    update_job_progress(db, job, 10, "Evaluation started")
    db.commit()

    try:
        result = execute_evaluation(db, evaluation)
        if job.status == "cancel_requested":
            evaluation.status = "cancelled"
            db.add(evaluation)
            cancel_job_after_claim(db, job)
            db.commit()
            return
        evaluation.progress = 100
        finalize_evaluation_success(db, evaluation, result)
        update_job_progress(db, job, 100, "Evaluation finished")
        db.commit()
    except Exception as exc:
        evaluation.progress = job.progress
        finalize_evaluation_failure(db, evaluation, str(exc))
        raise


def process_optimization_job(db: Session, job: Job) -> None:
    """处理优化类型任务，执行优化流程并更新状态。

    Args:
        db: 数据库会话。
        job: 待处理的优化任务对象。
    """
    if job.status == "cancel_requested":
        cancel_job_after_claim(db, job)
        return
    run = db.get(OptimizationRun, job.target_id)
    if run is None:
        raise bad_request(f"optimization run {job.target_id} not found")

    run.status = "running"
    run.progress = 5
    db.add(run)
    update_job_progress(db, job, 10, "Optimization started")
    db.commit()

    try:
        result = execute_optimization_run(db, run)
        if job.status == "cancel_requested":
            run.status = "cancelled"
            db.add(run)
            cancel_job_after_claim(db, job)
            db.commit()
            return
        run.progress = 100
        finalize_optimization_success(db, run, result)
        update_job_progress(db, job, 100, "Optimization finished")
        db.commit()
    except Exception as exc:
        run.progress = job.progress
        finalize_optimization_failure(db, run, str(exc))
        raise
