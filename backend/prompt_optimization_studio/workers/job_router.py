from sqlalchemy.orm import Session

from prompt_optimization_studio.core.exceptions import bad_request
from prompt_optimization_studio.models.evaluation import Evaluation
from prompt_optimization_studio.models.job import Job
from prompt_optimization_studio.models.optimization_run import OptimizationRun
from prompt_optimization_studio.services.evaluation_service import (
    execute_evaluation,
    finalize_evaluation_failure,
    finalize_evaluation_success,
)
from prompt_optimization_studio.services.optimization_service import (
    execute_optimization_run,
    finalize_optimization_failure,
    finalize_optimization_success,
)
from prompt_optimization_studio.services.job_service import cancel_job_after_claim, update_job_progress


def process_job(db: Session, job: Job) -> None:
    if job.job_type == "evaluation":
        process_evaluation_job(db, job)
        return
    if job.job_type == "optimization":
        process_optimization_job(db, job)
        return
    raise bad_request(f"unsupported job_type: {job.job_type}")


def process_evaluation_job(db: Session, job: Job) -> None:
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
