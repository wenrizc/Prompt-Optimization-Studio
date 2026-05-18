from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from prompt_optimization_studio.db.base import Base
from prompt_optimization_studio.models.mixins import TimestampMixin


class RunLog(TimestampMixin, Base):
    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text(), nullable=False)
    data_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
