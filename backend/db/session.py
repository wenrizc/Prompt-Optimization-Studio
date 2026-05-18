"""数据库会话管理模块。

负责创建数据库引擎、配置会话工厂，并提供依赖注入用的会话生成器。
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db_session() -> Generator[Session, None, None]:
    """获取数据库会话的依赖注入生成器。

    用于 FastAPI 路由中通过 Depends 注入数据库会话，请求结束后自动关闭会话。

    Yields:
        Session: SQLAlchemy 数据库会话实例。
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
