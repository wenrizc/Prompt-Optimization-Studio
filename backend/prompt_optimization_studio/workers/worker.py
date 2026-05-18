from sqlalchemy.orm import Session

from prompt_optimization_studio.db.session import SessionLocal
from prompt_optimization_studio.services.job_service import claim_next_job, complete_job, fail_job
from prompt_optimization_studio.workers.job_router import process_job


class LocalWorker:
    def __init__(self, worker_id: str) -> None:
        self.worker_id = worker_id

    def run_once(self, max_jobs: int = 1) -> list[int]:
        completed_job_ids: list[int] = []
        with SessionLocal() as db:
            for _ in range(max_jobs):
                job = claim_next_job(db, self.worker_id)
                if job is None:
                    db.commit()
                    break

                try:
                    process_job(db, job)
                    complete_job(db, job)
                    db.commit()
                    completed_job_ids.append(job.id)
                except Exception as exc:
                    fail_job(db, job, str(exc))
                    db.commit()
        return completed_job_ids
