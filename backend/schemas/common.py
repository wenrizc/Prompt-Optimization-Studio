"""公共基础模式定义。

提供所有 schema 共用的基类，包括 ORM 适配模型、带时间戳的响应模型和分页响应模型。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """支持从 ORM 属性构造并按字段名填充的基类模式。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TimestampedResponse(ORMModel):
    """带主键和时间戳的基础响应模式。"""

    id: int
    created_at: datetime
    updated_at: datetime


class PaginatedResponse(BaseModel):
    """通用分页响应基类，包含分页元数据。"""

    total: int
    page: int
    page_size: int
