"""制品（Artifact）数据模型，用于存储优化运行和评估产生的文件元数据。"""

from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base
from backend.models.mixins import TimestampMixin


class Artifact(TimestampMixin, Base):
    """制品模型，映射 artifacts 表。记录与优化运行或评估关联的文件制品信息。"""
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(512), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
