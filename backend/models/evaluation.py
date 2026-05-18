"""评估（Evaluation）数据模型，记录 Prompt 在指定数据集上的评估结果。"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base
from backend.models.mixins import TimestampMixin


class Evaluation(TimestampMixin, Base):
    """评估模型，映射 evaluations 表。记录 Prompt 评估的配置快照、评分及执行状态。"""
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"), nullable=False, index=True)
    prompt_id: Mapped[int] = mapped_column(ForeignKey("prompts.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score: Mapped[float | None] = mapped_column(nullable=True)
    metric_config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    model_config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    prompt_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    dataset_split_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    package_versions_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    random_seed: Mapped[int | None] = mapped_column(nullable=True)
    artifact_dir: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
