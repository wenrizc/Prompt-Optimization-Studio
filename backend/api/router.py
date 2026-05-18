"""API 路由聚合模块，将各子路由统一注册到主路由器。"""

from fastapi import APIRouter

from backend.api.routes.artifacts import router as artifacts_router
from backend.api.routes.custom_task_templates import (
    router as custom_task_templates_router,
)
from backend.api.routes.datasets import router as datasets_router
from backend.api.routes.evaluations import (
    router as evaluations_router,
)
from backend.api.routes.evaluations import (
    worker_router,
)
from backend.api.routes.jobs import router as jobs_router
from backend.api.routes.optimization_runs import (
    router as optimization_runs_router,
)
from backend.api.routes.projects import router as projects_router
from backend.api.routes.prompts import router as prompts_router
from backend.api.routes.run_logs import router as run_logs_router

api_router = APIRouter()
api_router.include_router(custom_task_templates_router)
api_router.include_router(projects_router)
api_router.include_router(prompts_router)
api_router.include_router(datasets_router)
api_router.include_router(evaluations_router)
api_router.include_router(optimization_runs_router)
api_router.include_router(worker_router)
api_router.include_router(jobs_router)
api_router.include_router(artifacts_router)
api_router.include_router(run_logs_router)
