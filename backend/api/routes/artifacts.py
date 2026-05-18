"""制品（Artifact）路由模块，提供制品列表查询、内容加载和下载接口。"""

import json

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from backend.api.dependencies import DbSession, get_db
from backend.core.exceptions import not_found
from backend.models.artifact import Artifact
from backend.schemas.artifact import (
    ArtifactListResponse,
    ArtifactManifestResponse,
    ArtifactResponse,
)
from backend.services.artifact_service import (
    list_owner_artifacts,
    load_artifact_content,
    load_owner_manifest,
    resolve_artifact_path,
)

router = APIRouter(prefix="/api/v1/artifacts", tags=["artifacts"])


@router.get("/{owner_type}/{owner_id}", response_model=ArtifactListResponse)
def get_owner_artifacts(
    owner_type: str, owner_id: int, db: DbSession = Depends(get_db)
) -> ArtifactListResponse:
    """获取指定所有者的制品列表。

    Args:
        owner_type: 所有者类型（如 evaluation、optimization_run）。
        owner_id: 所有者 ID。
        db: 数据库会话。

    Returns:
        包含制品列表和总数的响应。
    """
    items = list_owner_artifacts(db, owner_type, owner_id)
    return ArtifactListResponse(items=items, total=len(items))


@router.get("/{owner_type}/{owner_id}/manifest", response_model=ArtifactManifestResponse)
def get_owner_artifact_manifest(
    owner_type: str, owner_id: int, db: DbSession = Depends(get_db)
) -> ArtifactManifestResponse:
    """获取指定所有者的制品清单。

    Args:
        owner_type: 所有者类型。
        owner_id: 所有者 ID。
        db: 数据库会话。

    Returns:
        制品清单响应。
    """
    manifest = load_owner_manifest(db, owner_type, owner_id)
    return ArtifactManifestResponse(**manifest)


@router.get("/item/{artifact_id}")
def get_artifact_content(artifact_id: int, db: DbSession = Depends(get_db)) -> dict:
    """获取指定制品的元数据和内容。

    Args:
        artifact_id: 制品 ID。
        db: 数据库会话。

    Returns:
        包含制品元信息和解析后内容的字典。
    """
    loaded = load_artifact_content(db, artifact_id)
    return {
        "artifact": ArtifactResponse.model_validate(loaded["artifact"]).model_dump(),
        "content": json.loads(loaded["content"]),
    }


@router.get("/item/{artifact_id}/download")
def download_artifact(artifact_id: int, db: DbSession = Depends(get_db)) -> FileResponse:
    """下载指定制品的原始文件。

    Args:
        artifact_id: 制品 ID。
        db: 数据库会话。

    Returns:
        制品文件的 FileResponse。
    """
    artifact = db.get(Artifact, artifact_id)
    if artifact is None:
        raise not_found(f"Artifact {artifact_id} not found")
    resolved = resolve_artifact_path(artifact.relative_path)
    if not resolved.exists():
        raise not_found(f"Artifact file for {artifact_id} was not found on disk")
    return FileResponse(path=resolved, filename=resolved.name, media_type="application/json")
