from datetime import datetime
from typing import Any

from pydantic import BaseModel

from prompt_optimization_studio.schemas.common import ORMModel


class ArtifactResponse(ORMModel):
    id: int
    owner_type: str
    owner_id: int
    artifact_type: str
    relative_path: str
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ArtifactListResponse(BaseModel):
    items: list[ArtifactResponse]
    total: int


class ArtifactManifestResponse(BaseModel):
    owner_type: str
    owner_id: int
    artifacts: list[dict[str, Any]]
