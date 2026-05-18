"""制品（Artifact）相关的请求与响应模式。

定义制品信息查询、列表及清单的 API 响应结构。
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from backend.schemas.common import ORMModel


class ArtifactResponse(ORMModel):
    """单个制品的详细响应模式。"""
    id: int
    owner_type: str
    owner_id: int
    artifact_type: str
    relative_path: str
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ArtifactListResponse(BaseModel):
    """制品分页列表响应模式。"""

    items: list[ArtifactResponse]
    total: int


class ArtifactManifestResponse(BaseModel):
    """制品清单响应模式，包含某个拥有者的所有制品元数据。"""
    owner_type: str
    owner_id: int
    artifacts: list[dict[str, Any]]
