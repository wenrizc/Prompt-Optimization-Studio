"""数据集（Dataset）相关的请求与响应模式。

定义数据集的创建、导入、生成、拆分、质量报告以及数据样本的 CRUD 模式。
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from backend.core.constants import DATASET_SOURCE_TYPES
from backend.schemas.common import ORMModel


class DatasetCreate(BaseModel):
    """创建数据集的请求模式。"""

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
        """校验字段值是否为合法 JSON 对象。"""
        if not isinstance(value, dict):
            raise ValueError("must be a JSON object")
        return value


class DatasetResponse(ORMModel):
    """单个数据集的详细响应模式。"""
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
    """数据集分页列表响应模式。"""

    items: list[DatasetResponse]
    total: int
    source_types: list[str] = Field(default_factory=lambda: sorted(DATASET_SOURCE_TYPES))


class DatasetImportRequest(BaseModel):
    """导入数据集的请求模式，支持 JSON/JSONL/CSV 格式。"""

    model_config = {"populate_by_name": True}

    name: str = Field(min_length=1, max_length=255)
    project_id: int
    file_format: Literal["json", "jsonl", "csv"]
    content: str = Field(min_length=1)
    input_field: str = Field(default="text", min_length=1)
    output_field: str = Field(default="expected_output", min_length=1)
    metadata_fields: list[str] = Field(default_factory=list)
    split: Literal["train", "dev", "test", "unassigned"] = "unassigned"
    schema_definition: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="schema_json",
        serialization_alias="schema_json",
    )


class DatasetImportResponse(BaseModel):
    """导入数据集的响应模式，包含导入统计信息。"""
    dataset: DatasetResponse
    imported_examples: int
    import_path: str


class DatasetGenerateRequest(BaseModel):
    """合成生成数据集的请求模式。"""
    project_id: int
    name: str = Field(min_length=1, max_length=255)
    command: str = Field(min_length=1)
    count: int = Field(default=20, ge=1, le=500)


class DatasetGenerateResponse(BaseModel):
    """合成生成数据集的响应模式，包含生成统计信息。"""
    dataset: DatasetResponse
    generated_examples: int


class DatasetExampleCreate(BaseModel):
    """创建数据样本的请求模式。"""
    split: Literal["train", "dev", "test", "unassigned"] = "unassigned"
    input_json: dict[str, Any] = Field(default_factory=dict)
    expected_output_json: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class DatasetExampleUpdate(BaseModel):
    """更新数据样本的请求模式，所有字段可选。"""
    split: Literal["train", "dev", "test", "unassigned"] | None = None
    input_json: dict[str, Any] | None = None
    expected_output_json: dict[str, Any] | None = None
    metadata_json: dict[str, Any] | None = None


class DatasetExampleResponse(ORMModel):
    """单个数据样本的详细响应模式。"""
    id: int
    dataset_id: int
    split: str
    input_json: dict[str, Any]
    expected_output_json: dict[str, Any]
    metadata_json: dict[str, Any]
    content_hash: str
    created_at: datetime
    updated_at: datetime


class DatasetExampleListResponse(BaseModel):
    """数据样本分页列表响应模式。"""
    items: list[DatasetExampleResponse]
    total: int
    page: int
    page_size: int


class DatasetSplitRequest(BaseModel):
    """数据集拆分（train/dev/test）的请求模式。"""
    train_ratio: float = Field(default=0.7, ge=0, le=1)
    dev_ratio: float = Field(default=0.15, ge=0, le=1)
    test_ratio: float = Field(default=0.15, ge=0, le=1)
    stratify_by: str | None = None


class DatasetSplitResponse(BaseModel):
    """数据集拆分的响应模式，包含各拆分分配数量和质量摘要。"""
    assignments: dict[str, int]
    quality_summary_json: dict[str, Any]


class DatasetQualityReportResponse(BaseModel):
    """数据集质量报告的响应模式。"""
    dataset_id: int
    quality_summary_json: dict[str, Any]
