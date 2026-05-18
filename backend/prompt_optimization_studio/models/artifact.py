from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from prompt_optimization_studio.db.base import Base
from prompt_optimization_studio.models.mixins import TimestampMixin


class Artifact(TimestampMixin, Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(512), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
