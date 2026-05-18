"""提示词（Prompt）数据模型，存储系统提示词和用户模板。"""

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base
from backend.models.mixins import TimestampMixin


class Prompt(TimestampMixin, Base):
    """提示词模型，映射 prompts 表。每个 Prompt 属于某个项目，具有唯一的项目+名称+版本约束。"""

    __tablename__ = "prompts"
    __table_args__ = (UniqueConstraint("project_id", "name", "version", name="uq_prompt_version"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text(), nullable=False, default="")
    user_template: Mapped[str] = mapped_column(Text(), nullable=False)
    output_schema_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
