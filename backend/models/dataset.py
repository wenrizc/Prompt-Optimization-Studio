"""数据集（Dataset）及数据样本（DatasetExample）数据模型。"""

from sqlalchemy import JSON, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base
from backend.models.mixins import TimestampMixin


class Dataset(TimestampMixin, Base):
    """数据集模型，映射 datasets 表。存储数据集的元信息，包括来源、生成配置和质量摘要。"""
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    command: Mapped[str | None] = mapped_column(Text(), nullable=True)
    generation_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    parent_dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id"), nullable=True)
    quality_summary_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class DatasetExample(TimestampMixin, Base):
    """数据样本模型，映射 dataset_examples 表。存储数据集中单条样本的输入、期望输出与划分。"""
    __tablename__ = "dataset_examples"
    __table_args__ = (
        Index("ix_dataset_examples_dataset_split", "dataset_id", "split"),
        Index("ix_dataset_examples_dataset_content_hash", "dataset_id", "content_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"), nullable=False, index=True)
    split: Mapped[str] = mapped_column(String(32), nullable=False, default="unassigned")
    input_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    expected_output_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
