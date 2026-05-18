import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from prompt_optimization_studio.core.config import get_settings
from prompt_optimization_studio.core.constants import ARTIFACT_OWNER_TYPES
from prompt_optimization_studio.core.exceptions import bad_request, not_found
from prompt_optimization_studio.models.artifact import Artifact


def write_owner_artifact(
    db: Session,
    owner_type: str,
    owner_id: int,
    artifact_type: str,
    file_name: str,
    payload: Any,
) -> Artifact:
    settings = get_settings()
    owner_dir = settings.artifacts_dir / _owner_dir(owner_type, owner_id)
    owner_dir.mkdir(parents=True, exist_ok=True)

    target_path = owner_dir / file_name
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    target_path.write_text(serialized, encoding="utf-8")

    relative_path = target_path.relative_to(settings.data_dir).as_posix()
    metadata = {
        "file_name": file_name,
        "size_bytes": target_path.stat().st_size,
        "sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
    }

    artifact = _upsert_artifact(
        db=db,
        owner_type=owner_type,
        owner_id=owner_id,
        artifact_type=artifact_type,
        relative_path=relative_path,
        metadata_json=metadata,
    )
    write_manifest(db, owner_type, owner_id)
    return artifact


def list_owner_artifacts(db: Session, owner_type: str, owner_id: int) -> list[Artifact]:
    ensure_valid_owner_type(owner_type)
    return list(
        db.scalars(
            select(Artifact)
            .where(Artifact.owner_type == owner_type, Artifact.owner_id == owner_id)
            .order_by(Artifact.created_at.asc())
        )
    )


def load_artifact_content(db: Session, artifact_id: int) -> dict[str, Any]:
    artifact = db.get(Artifact, artifact_id)
    if artifact is None:
        raise not_found(f"Artifact {artifact_id} not found")

    resolved = resolve_artifact_path(artifact.relative_path)
    if not resolved.exists():
        raise not_found(f"Artifact file for {artifact_id} was not found on disk")
    return {
        "artifact": artifact,
        "content": resolved.read_text(encoding="utf-8"),
    }


def load_owner_manifest(db: Session, owner_type: str, owner_id: int) -> dict[str, Any]:
    ensure_valid_owner_type(owner_type)
    settings = get_settings()
    owner_dir = settings.artifacts_dir / _owner_dir(owner_type, owner_id)
    manifest_path = owner_dir / "manifest.json"
    resolved = manifest_path.resolve()
    root = settings.data_dir.resolve()
    if root not in resolved.parents and resolved != root:
        raise bad_request("manifest path escaped data directory")
    if not manifest_path.exists():
        raise not_found(f"Manifest for {owner_type} {owner_id} not found")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def write_manifest(db: Session, owner_type: str, owner_id: int) -> None:
    ensure_valid_owner_type(owner_type)
    settings = get_settings()
    owner_dir = settings.artifacts_dir / _owner_dir(owner_type, owner_id)
    owner_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = owner_dir / "manifest.json"
    artifacts = list_owner_artifacts(db, owner_type, owner_id)
    manifest = {
        "owner_type": owner_type,
        "owner_id": owner_id,
        "artifacts": [
            {
                "artifact_type": artifact.artifact_type,
                "relative_path": artifact.relative_path,
                "metadata_json": artifact.metadata_json,
            }
            for artifact in artifacts
        ],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_valid_owner_type(owner_type: str) -> None:
    if owner_type not in ARTIFACT_OWNER_TYPES:
        raise bad_request(f"unsupported artifact owner_type: {owner_type}")


def resolve_artifact_path(relative_path: str) -> Path:
    settings = get_settings()
    resolved = (settings.data_dir / relative_path).resolve()
    root = settings.data_dir.resolve()
    if root not in resolved.parents and resolved != root:
        raise bad_request("artifact path escaped data directory")
    return resolved


def _upsert_artifact(
    db: Session,
    owner_type: str,
    owner_id: int,
    artifact_type: str,
    relative_path: str,
    metadata_json: dict[str, Any],
) -> Artifact:
    artifact = db.scalar(
        select(Artifact).where(
            Artifact.owner_type == owner_type,
            Artifact.owner_id == owner_id,
            Artifact.artifact_type == artifact_type,
        )
    )
    if artifact is None:
        artifact = Artifact(
            owner_type=owner_type,
            owner_id=owner_id,
            artifact_type=artifact_type,
            relative_path=relative_path,
            metadata_json=metadata_json,
        )
    else:
        artifact.relative_path = relative_path
        artifact.metadata_json = metadata_json

    db.add(artifact)
    db.flush()
    return artifact


def _owner_dir(owner_type: str, owner_id: int) -> str:
    return f"{owner_type}s/{owner_id}"
