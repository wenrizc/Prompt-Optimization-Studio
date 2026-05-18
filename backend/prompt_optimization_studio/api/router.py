from fastapi import APIRouter

from prompt_optimization_studio.api.routes.artifacts import router as artifacts_router
from prompt_optimization_studio.api.routes.datasets import router as datasets_router
from prompt_optimization_studio.api.routes.evaluations import (
    router as evaluations_router,
    worker_router,
)
from prompt_optimization_studio.api.routes.health import router as health_router
from prompt_optimization_studio.api.routes.jobs import router as jobs_router
from prompt_optimization_studio.api.routes.optimization_runs import (
    router as optimization_runs_router,
)
from prompt_optimization_studio.api.routes.projects import router as projects_router
from prompt_optimization_studio.api.routes.prompts import router as prompts_router
from prompt_optimization_studio.api.routes.run_logs import router as run_logs_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(projects_router)
api_router.include_router(prompts_router)
api_router.include_router(datasets_router)
api_router.include_router(evaluations_router)
api_router.include_router(optimization_runs_router)
api_router.include_router(worker_router)
api_router.include_router(jobs_router)
api_router.include_router(artifacts_router)
api_router.include_router(run_logs_router)
