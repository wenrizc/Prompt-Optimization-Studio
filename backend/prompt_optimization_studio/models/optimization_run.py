from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from prompt_optimization_studio.db.base import Base
from prompt_optimization_studio.models.mixins import TimestampMixin


class OptimizationRun(TimestampMixin, Base):
    __tablename__ = "optimization_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"), nullable=False, index=True)
    prompt_id: Mapped[int] = mapped_column(ForeignKey("prompts.id"), nullable=False, index=True)
    optimizer_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    baseline_score: Mapped[float | None] = mapped_column(nullable=True)
    optimized_score: Mapped[float | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    artifact_dir: Mapped[str | None] = mapped_column(String(512), nullable=True)
    prompt_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    dataset_split_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    model_config_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    optimizer_config_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metric_config_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    package_versions_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    random_seed: Mapped[int | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
