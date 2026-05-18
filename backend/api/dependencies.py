"""FastAPI 依赖注入模块，提供数据库会话等公共依赖。"""

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.db.session import get_db_session

DbSession = Session


def get_db(session: DbSession = Depends(get_db_session)) -> DbSession:
    """获取数据库会话的 FastAPI 依赖。"""
    return session
