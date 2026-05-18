"""本地任务执行器模块，负责从队列中领取并执行后台任务。"""

from backend.db.session import SessionLocal
from backend.services.job_service import claim_next_job, complete_job, fail_job
from backend.workers.job_router import process_job


class LocalWorker:
    """本地后台任务执行器，从数据库队列中领取任务并执行。"""

    def __init__(self, worker_id: str) -> None:
        """初始化 Worker 实例。

        Args:
            worker_id: Worker 标识符，用于任务领取时标记执行者。
        """
        self.worker_id = worker_id

    def run_once(self, max_jobs: int = 1) -> list[int]:
        """执行一次任务轮询，领取并处理最多 max_jobs 个任务。

        Args:
            max_jobs: 本次轮询最多执行的任务数。

        Returns:
            成功完成的任务 ID 列表。
        """
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
