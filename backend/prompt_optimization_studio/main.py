from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from prompt_optimization_studio.api.router import api_router
from prompt_optimization_studio.core.config import get_settings
from prompt_optimization_studio.core.runtime import ensure_runtime_directories


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_runtime_directories()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app


app = create_app()
