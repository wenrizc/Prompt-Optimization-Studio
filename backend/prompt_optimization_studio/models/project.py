from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from prompt_optimization_studio.db.base import Base
from prompt_optimization_studio.models.mixins import TimestampMixin


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    task_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    task_key: Mapped[str] = mapped_column(String(64), nullable=False)
    task_display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    task_description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    input_schema_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_schema_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    default_metric_config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    task_definition_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    report_profile_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
