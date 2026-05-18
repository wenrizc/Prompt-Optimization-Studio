"""自定义任务模板数据模型。"""

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base
from backend.models.mixins import TimestampMixin


class CustomTaskTemplate(TimestampMixin, Base):
    """自定义任务模板模型，用于持久化跨浏览器共享的任务契约。"""

    __tablename__ = "custom_task_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    task_display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    task_description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    input_schema_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_schema_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    default_metric_config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    task_definition_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    report_profile_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
