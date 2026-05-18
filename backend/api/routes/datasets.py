"""数据集路由模块，提供数据集的增删改查、导入、生成、拆分和质量报告接口。"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from backend.api.dependencies import DbSession, get_db
from backend.core.config import get_settings
from backend.core.exceptions import bad_request, not_found
from backend.models.dataset import Dataset, DatasetExample
from backend.models.project import Project
from backend.schemas.dataset import (
    DatasetCreate,
    DatasetExampleCreate,
    DatasetExampleListResponse,
    DatasetExampleResponse,
    DatasetExampleUpdate,
    DatasetGenerateRequest,
    DatasetGenerateResponse,
    DatasetImportRequest,
    DatasetImportResponse,
    DatasetListResponse,
    DatasetQualityReportResponse,
    DatasetResponse,
    DatasetSplitRequest,
    DatasetSplitResponse,
)
from backend.services.dataset_generation import create_generated_dataset
from backend.services.dataset_service import (
    apply_dataset_split,
    get_dataset_or_404,
    import_dataset_examples,
    parse_import_content,
    refresh_dataset_quality_summary,
    write_import_snapshot,
)
from backend.services.validators import (
    compute_example_content_hash,
    ensure_json_schema_object,
)

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
def create_dataset(payload: DatasetCreate, db: DbSession = Depends(get_db)) -> Dataset:
    """创建新数据集。

    Args:
        payload: 数据集创建请求数据。
        db: 数据库会话。

    Returns:
        新创建的数据集对象。
    """
    project = db.get(Project, payload.project_id)
    if project is None:
        raise not_found(f"Project {payload.project_id} not found")
    ensure_json_schema_object(payload.schema_definition, "schema_json")
    ensure_json_schema_object(payload.quality_summary_json, "quality_summary_json")

    values = payload.model_dump(by_alias=True)
    dataset = Dataset(**values)
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


@router.post("/import", response_model=DatasetImportResponse, status_code=status.HTTP_201_CREATED)
def import_dataset(
    payload: DatasetImportRequest,
    db: DbSession = Depends(get_db),
) -> DatasetImportResponse:
    """从外部文件导入数据集。

    Args:
        payload: 数据集导入请求数据，包含文件内容和解析配置。
        db: 数据库会话。

    Returns:
        包含导入数据集信息、导入条目数和快照路径的响应。
    """
    project = db.get(Project, payload.project_id)
    if project is None:
        raise not_found(f"Project {payload.project_id} not found")

    ensure_json_schema_object(payload.schema_definition, "schema_json")
    dataset = Dataset(
        project_id=payload.project_id,
        name=payload.name,
        source_type="imported",
        schema_json=payload.schema_definition,
        quality_summary_json={},
        status="active",
    )
    db.add(dataset)
    db.flush()

    parsed_examples = parse_import_content(
        content=payload.content,
        file_format=payload.file_format,
        input_field=payload.input_field,
        output_field=payload.output_field,
        metadata_fields=payload.metadata_fields,
        input_schema_json=project.input_schema_json,
        output_schema_json=project.output_schema_json,
    )
    import_path = write_import_snapshot(dataset.id, payload.file_format, payload.content)
    created_examples = import_dataset_examples(
        db,
        dataset,
        parsed_examples,
        split=payload.split,
    )
    return DatasetImportResponse(
        dataset=dataset,
        imported_examples=len(created_examples),
        import_path=import_path,
    )


@router.post(
    "/generate", response_model=DatasetGenerateResponse, status_code=status.HTTP_201_CREATED
)
def generate_dataset(
    payload: DatasetGenerateRequest,
    db: DbSession = Depends(get_db),
) -> DatasetGenerateResponse:
    """通过 LLM 自动生成数据集。

    Args:
        payload: 数据集生成请求数据，包含生成指令和模型配置。
        db: 数据库会话。

    Returns:
        包含生成的数据集和生成条目数的响应。
    """
    project = db.get(Project, payload.project_id)
    if project is None:
        raise not_found(f"Project {payload.project_id} not found")
    settings = get_settings()
    if payload.count > settings.max_generated_examples:
        raise bad_request(
            f"count exceeds max_generated_examples={settings.max_generated_examples}"
        )

    dataset, generated_examples = create_generated_dataset(
        db=db,
        project=project,
        name=payload.name,
        command=payload.command,
        count=payload.count,
    )
    return DatasetGenerateResponse(dataset=dataset, generated_examples=generated_examples)


@router.get("", response_model=DatasetListResponse)
def list_datasets(
    project_id: int | None = Query(default=None),
    db: DbSession = Depends(get_db),
) -> DatasetListResponse:
    """获取数据集列表，支持按项目 ID 筛选。

    Args:
        project_id: 可选的项目 ID 筛选条件。
        db: 数据库会话。

    Returns:
        包含数据集列表和总数的响应。
    """
    query = select(Dataset).order_by(Dataset.created_at.desc())
    if project_id is not None:
        query = query.where(Dataset.project_id == project_id)
    items = list(db.scalars(query))
    return DatasetListResponse(items=items, total=len(items))


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(dataset_id: int, db: DbSession = Depends(get_db)) -> Dataset:
    """获取指定数据集详情。

    Args:
        dataset_id: 数据集 ID。
        db: 数据库会话。

    Returns:
        数据集对象。
    """
    return get_dataset_or_404(db, dataset_id)


@router.post(
    "/{dataset_id}/examples",
    response_model=DatasetExampleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_dataset_example(
    dataset_id: int,
    payload: DatasetExampleCreate,
    db: DbSession = Depends(get_db),
) -> DatasetExample:
    """向指定数据集添加新样本。

    Args:
        dataset_id: 数据集 ID。
        payload: 样本创建请求数据。
        db: 数据库会话。

    Returns:
        新创建的数据集样本对象。
    """
    dataset = get_dataset_or_404(db, dataset_id)
    content_hash = compute_example_content_hash(payload.input_json, payload.expected_output_json)
    example = DatasetExample(
        dataset_id=dataset_id, content_hash=content_hash, **payload.model_dump()
    )
    db.add(example)
    refresh_dataset_quality_summary(db, dataset)
    db.commit()
    db.refresh(example)
    return example


@router.get("/{dataset_id}/examples", response_model=DatasetExampleListResponse)
def list_dataset_examples(
    dataset_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    split: str | None = Query(default=None),
    db: DbSession = Depends(get_db),
) -> DatasetExampleListResponse:
    """分页获取数据集样本列表，支持按拆分和质量状态筛选。

    Args:
        dataset_id: 数据集 ID。
        page: 页码，从 1 开始。
        page_size: 每页条数，最大 200。
        split: 可选的拆分类型筛选条件。
        db: 数据库会话。

    Returns:
        包含样本列表、总数和分页信息的响应。
    """
    get_dataset_or_404(db, dataset_id)

    query = select(DatasetExample).where(DatasetExample.dataset_id == dataset_id)
    count_query = select(func.count(DatasetExample.id)).where(
        DatasetExample.dataset_id == dataset_id
    )
    if split is not None:
        query = query.where(DatasetExample.split == split)
        count_query = count_query.where(DatasetExample.split == split)

    total = db.scalar(count_query) or 0
    items = list(
        db.scalars(
            query.order_by(DatasetExample.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return DatasetExampleListResponse(items=items, total=total, page=page, page_size=page_size)


@router.patch("/{dataset_id}/examples/{example_id}", response_model=DatasetExampleResponse)
def update_dataset_example(
    dataset_id: int,
    example_id: int,
    payload: DatasetExampleUpdate,
    db: DbSession = Depends(get_db),
) -> DatasetExample:
    """更新数据集中的指定样本。

    Args:
        dataset_id: 数据集 ID。
        example_id: 样本 ID。
        payload: 样本更新请求数据。
        db: 数据库会话。

    Returns:
        更新后的样本对象。
    """
    example = db.get(DatasetExample, example_id)
    if example is None or example.dataset_id != dataset_id:
        raise not_found(f"Dataset example {example_id} not found in dataset {dataset_id}")
    dataset = get_dataset_or_404(db, dataset_id)

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(example, key, value)

    if payload.input_json is not None or payload.expected_output_json is not None:
        example.content_hash = compute_example_content_hash(
            example.input_json, example.expected_output_json
        )

    db.add(example)
    refresh_dataset_quality_summary(db, dataset)
    db.commit()
    db.refresh(example)
    return example


@router.post("/{dataset_id}/split", response_model=DatasetSplitResponse)
def split_dataset(
    dataset_id: int,
    payload: DatasetSplitRequest,
    db: DbSession = Depends(get_db),
) -> DatasetSplitResponse:
    """对数据集执行训练/验证/测试拆分。

    Args:
        dataset_id: 数据集 ID。
        payload: 拆分请求数据，包含各拆分的比例配置。
        db: 数据库会话。

    Returns:
        包含拆分分配结果和质量摘要的响应。
    """
    dataset = get_dataset_or_404(db, dataset_id)
    assignments = apply_dataset_split(
        db,
        dataset,
        train_ratio=payload.train_ratio,
        dev_ratio=payload.dev_ratio,
        test_ratio=payload.test_ratio,
        stratify_by=payload.stratify_by,
    )
    return DatasetSplitResponse(
        assignments=assignments, quality_summary_json=dataset.quality_summary_json
    )


@router.get("/{dataset_id}/quality-report", response_model=DatasetQualityReportResponse)
def get_dataset_quality_report(
    dataset_id: int, db: DbSession = Depends(get_db)
) -> DatasetQualityReportResponse:
    """获取数据集质量报告，刷新并返回质量摘要。

    Args:
        dataset_id: 数据集 ID。
        db: 数据库会话。

    Returns:
        包含数据集 ID 和质量摘要的响应。
    """
    dataset = get_dataset_or_404(db, dataset_id)
    refresh_dataset_quality_summary(db, dataset)
    db.commit()
    db.refresh(dataset)
    return DatasetQualityReportResponse(
        dataset_id=dataset.id, quality_summary_json=dataset.quality_summary_json
    )
