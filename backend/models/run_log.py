"""运行日志（RunLog）数据模型，记录评估和优化运行的详细日志。"""

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base
from backend.models.mixins import TimestampMixin


class RunLog(TimestampMixin, Base):
    """运行日志模型，映射 run_logs 表。按运行类型和 ID 关联，存储级别、消息及附加数据。"""
    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text(), nullable=False)
    data_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
