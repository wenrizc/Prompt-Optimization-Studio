"""FastAPI 应用工厂与生命周期管理模块。

负责创建 FastAPI 应用实例、注册中间件、挂载路由及前端静态资源。
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import backend.models  # noqa: F401
from backend.api.router import api_router
from backend.core.config import get_settings
from backend.core.runtime import ensure_runtime_directories
from backend.db.base import Base
from backend.db.session import engine

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期上下文管理器，在启动时确保运行时目录存在。"""
    ensure_runtime_directories()
    Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    """创建并返回配置完整的 FastAPI 应用实例。

    Returns:
        配置好 CORS 中间件、API 路由和前端静态资源的 FastAPI 应用。
    """
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    static_dir = settings.static_dir
    if static_dir is None:
        static_dir = _PROJECT_ROOT / "frontend" / "out"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


app = create_app()
