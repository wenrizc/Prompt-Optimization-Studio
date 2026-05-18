from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from prompt_optimization_studio.core.constants import DATASET_SOURCE_TYPES
from prompt_optimization_studio.schemas.common import ORMModel


class DatasetCreate(BaseModel):
    model_config = {"populate_by_name": True}

    project_id: int
    name: str = Field(min_length=1, max_length=255)
    source_type: Literal["manual_upload", "synthetic_generated", "edited", "imported"]
    schema_definition: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="schema_json",
        serialization_alias="schema_json",
    )
    command: str | None = None
    generation_model: str | None = None
    parent_dataset_id: int | None = None
    quality_summary_json: dict[str, Any] = Field(default_factory=dict)
    status: Literal["active", "archived"] = "active"

    @field_validator("schema_definition", "quality_summary_json")
    @classmethod
    def validate_json_object(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("must be a JSON object")
        return value


class DatasetResponse(ORMModel):
    id: int
    project_id: int
    name: str
    source_type: str
    schema_definition: dict[str, Any] = Field(
        validation_alias="schema_json",
        serialization_alias="schema_json",
    )
    command: str | None
    generation_model: str | None
    parent_dataset_id: int | None
    quality_summary_json: dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


class DatasetListResponse(BaseModel):
    items: list[DatasetResponse]
    total: int
    source_types: list[str] = Field(default_factory=lambda: sorted(DATASET_SOURCE_TYPES))


class DatasetImportRequest(BaseModel):
    model_config = {"populate_by_name": True}

    name: str = Field(min_length=1, max_length=255)
    project_id: int
    file_format: Literal["json", "jsonl", "csv"]
    content: str = Field(min_length=1)
    input_field: str = Field(default="text", min_length=1)
    output_field: str = Field(default="expected_output", min_length=1)
    metadata_fields: list[str] = Field(default_factory=list)
    split: Literal["train", "dev", "test", "unassigned"] = "unassigned"
    quality_status: Literal["unchecked", "accepted", "rejected", "needs_review"] = "unchecked"
    schema_definition: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="schema_json",
        serialization_alias="schema_json",
    )


class DatasetImportResponse(BaseModel):
    dataset: DatasetResponse
    imported_examples: int
    import_path: str


class DatasetGenerateRequest(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=255)
    command: str = Field(min_length=1)
    count: int = Field(default=20, ge=1, le=500)
    generation_model: str = Field(default="mock")
    quality_status: Literal["unchecked", "accepted", "rejected", "needs_review"] = "unchecked"


class DatasetGenerateResponse(BaseModel):
    dataset: DatasetResponse
    generated_examples: int


class DatasetExampleCreate(BaseModel):
    split: Literal["train", "dev", "test", "unassigned"] = "unassigned"
    input_json: dict[str, Any] = Field(default_factory=dict)
    expected_output_json: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    quality_status: Literal["unchecked", "accepted", "rejected", "needs_review"] = "unchecked"


class DatasetExampleUpdate(BaseModel):
    split: Literal["train", "dev", "test", "unassigned"] | None = None
    input_json: dict[str, Any] | None = None
    expected_output_json: dict[str, Any] | None = None
    metadata_json: dict[str, Any] | None = None
    quality_status: Literal["unchecked", "accepted", "rejected", "needs_review"] | None = None


class DatasetExampleResponse(ORMModel):
    id: int
    dataset_id: int
    split: str
    input_json: dict[str, Any]
    expected_output_json: dict[str, Any]
    metadata_json: dict[str, Any]
    quality_status: str
    content_hash: str
    created_at: datetime
    updated_at: datetime


class DatasetExampleListResponse(BaseModel):
    items: list[DatasetExampleResponse]
    total: int
    page: int
    page_size: int


class DatasetExampleBulkReviewRequest(BaseModel):
    example_ids: list[int] = Field(min_length=1)
    quality_status: Literal["unchecked", "accepted", "rejected", "needs_review"]


class DatasetExampleBulkReviewResponse(BaseModel):
    updated: int


class DatasetSplitRequest(BaseModel):
    train_ratio: float = Field(default=0.7, ge=0, le=1)
    dev_ratio: float = Field(default=0.15, ge=0, le=1)
    test_ratio: float = Field(default=0.15, ge=0, le=1)
    stratify_by: str | None = None
    include_needs_review: bool = False


class DatasetSplitResponse(BaseModel):
    assignments: dict[str, int]
    quality_summary_json: dict[str, Any]


class DatasetQualityReportResponse(BaseModel):
    dataset_id: int
    quality_summary_json: dict[str, Any]
