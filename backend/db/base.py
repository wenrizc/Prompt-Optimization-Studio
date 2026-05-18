"""SQLAlchemy 声明式基类模块。

提供所有 ORM 模型的公共基类，用于定义数据库表与 Python 对象之间的映射关系。
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。

    所有 ORM 模型均应继承此类，以便 SQLAlchemy 自动管理元数据和表映射。
    """
    pass
