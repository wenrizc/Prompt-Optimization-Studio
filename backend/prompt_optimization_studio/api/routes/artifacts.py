import json

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from prompt_optimization_studio.api.dependencies import DbSession, get_db
from prompt_optimization_studio.core.exceptions import not_found
from prompt_optimization_studio.models.artifact import Artifact
from prompt_optimization_studio.schemas.artifact import ArtifactListResponse, ArtifactManifestResponse, ArtifactResponse
from prompt_optimization_studio.services.artifact_service import (
    list_owner_artifacts,
    load_artifact_content,
    load_owner_manifest,
    resolve_artifact_path,
)

router = APIRouter(prefix="/api/v1/artifacts", tags=["artifacts"])


@router.get("/{owner_type}/{owner_id}", response_model=ArtifactListResponse)
def get_owner_artifacts(owner_type: str, owner_id: int, db: DbSession = Depends(get_db)) -> ArtifactListResponse:
    items = list_owner_artifacts(db, owner_type, owner_id)
    return ArtifactListResponse(items=items, total=len(items))


@router.get("/{owner_type}/{owner_id}/manifest", response_model=ArtifactManifestResponse)
def get_owner_artifact_manifest(owner_type: str, owner_id: int, db: DbSession = Depends(get_db)) -> ArtifactManifestResponse:
    manifest = load_owner_manifest(db, owner_type, owner_id)
    return ArtifactManifestResponse(**manifest)


@router.get("/item/{artifact_id}")
def get_artifact_content(artifact_id: int, db: DbSession = Depends(get_db)) -> dict:
    loaded = load_artifact_content(db, artifact_id)
    return {
        "artifact": ArtifactResponse.model_validate(loaded["artifact"]).model_dump(),
        "content": json.loads(loaded["content"]),
    }


@router.get("/item/{artifact_id}/download")
def download_artifact(artifact_id: int, db: DbSession = Depends(get_db)) -> FileResponse:
    artifact = db.get(Artifact, artifact_id)
    if artifact is None:
        raise not_found(f"Artifact {artifact_id} not found")
    resolved = resolve_artifact_path(artifact.relative_path)
    if not resolved.exists():
        raise not_found(f"Artifact file for {artifact_id} was not found on disk")
    return FileResponse(path=resolved, filename=resolved.name, media_type="application/json")
