from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from prompt_optimization_studio.api.dependencies import DbSession, get_db
from prompt_optimization_studio.core.exceptions import not_found
from prompt_optimization_studio.models.dataset import Dataset, DatasetExample
from prompt_optimization_studio.models.project import Project
from prompt_optimization_studio.schemas.dataset import (
    DatasetCreate,
    DatasetExampleBulkReviewRequest,
    DatasetExampleBulkReviewResponse,
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
from prompt_optimization_studio.services.dataset_service import (
    apply_dataset_split,
    get_dataset_or_404,
    import_dataset_examples,
    parse_import_content,
    refresh_dataset_quality_summary,
    write_import_snapshot,
)
from prompt_optimization_studio.services.dataset_generation import create_generated_dataset
from prompt_optimization_studio.services.validators import compute_example_content_hash, ensure_json_schema_object

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
def create_dataset(payload: DatasetCreate, db: DbSession = Depends(get_db)) -> Dataset:
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
    )
    import_path = write_import_snapshot(dataset.id, payload.file_format, payload.content)
    created_examples = import_dataset_examples(
        db,
        dataset,
        parsed_examples,
        split=payload.split,
        quality_status=payload.quality_status,
    )
    return DatasetImportResponse(
        dataset=dataset,
        imported_examples=len(created_examples),
        import_path=import_path,
    )


@router.post("/generate", response_model=DatasetGenerateResponse, status_code=status.HTTP_201_CREATED)
def generate_dataset(
    payload: DatasetGenerateRequest,
    db: DbSession = Depends(get_db),
) -> DatasetGenerateResponse:
    project = db.get(Project, payload.project_id)
    if project is None:
        raise not_found(f"Project {payload.project_id} not found")

    dataset, generated_examples = create_generated_dataset(
        db=db,
        project=project,
        name=payload.name,
        command=payload.command,
        count=payload.count,
        generation_model=payload.generation_model,
        quality_status=payload.quality_status,
    )
    return DatasetGenerateResponse(dataset=dataset, generated_examples=generated_examples)


@router.get("", response_model=DatasetListResponse)
def list_datasets(
    project_id: int | None = Query(default=None),
    db: DbSession = Depends(get_db),
) -> DatasetListResponse:
    query = select(Dataset).order_by(Dataset.created_at.desc())
    if project_id is not None:
        query = query.where(Dataset.project_id == project_id)
    items = list(db.scalars(query))
    return DatasetListResponse(items=items, total=len(items))


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(dataset_id: int, db: DbSession = Depends(get_db)) -> Dataset:
    return get_dataset_or_404(db, dataset_id)


@router.post("/{dataset_id}/examples", response_model=DatasetExampleResponse, status_code=status.HTTP_201_CREATED)
def create_dataset_example(
    dataset_id: int,
    payload: DatasetExampleCreate,
    db: DbSession = Depends(get_db),
) -> DatasetExample:
    dataset = get_dataset_or_404(db, dataset_id)
    content_hash = compute_example_content_hash(payload.input_json, payload.expected_output_json)
    example = DatasetExample(dataset_id=dataset_id, content_hash=content_hash, **payload.model_dump())
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
    quality_status: str | None = Query(default=None),
    db: DbSession = Depends(get_db),
) -> DatasetExampleListResponse:
    get_dataset_or_404(db, dataset_id)

    query = select(DatasetExample).where(DatasetExample.dataset_id == dataset_id)
    count_query = select(func.count(DatasetExample.id)).where(DatasetExample.dataset_id == dataset_id)
    if split is not None:
        query = query.where(DatasetExample.split == split)
        count_query = count_query.where(DatasetExample.split == split)
    if quality_status is not None:
        query = query.where(DatasetExample.quality_status == quality_status)
        count_query = count_query.where(DatasetExample.quality_status == quality_status)

    total = db.scalar(count_query) or 0
    items = list(
        db.scalars(
            query.order_by(DatasetExample.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
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
    example = db.get(DatasetExample, example_id)
    if example is None or example.dataset_id != dataset_id:
        raise not_found(f"Dataset example {example_id} not found in dataset {dataset_id}")
    dataset = get_dataset_or_404(db, dataset_id)

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(example, key, value)

    if payload.input_json is not None or payload.expected_output_json is not None:
        example.content_hash = compute_example_content_hash(example.input_json, example.expected_output_json)

    db.add(example)
    refresh_dataset_quality_summary(db, dataset)
    db.commit()
    db.refresh(example)
    return example


@router.post("/{dataset_id}/examples/review", response_model=DatasetExampleBulkReviewResponse)
def bulk_review_dataset_examples(
    dataset_id: int,
    payload: DatasetExampleBulkReviewRequest,
    db: DbSession = Depends(get_db),
) -> DatasetExampleBulkReviewResponse:
    dataset = get_dataset_or_404(db, dataset_id)

    query = select(DatasetExample).where(
        DatasetExample.dataset_id == dataset_id,
        DatasetExample.id.in_(payload.example_ids),
    )
    examples = list(db.scalars(query))
    for example in examples:
        example.quality_status = payload.quality_status
        db.add(example)

    refresh_dataset_quality_summary(db, dataset)
    db.commit()
    return DatasetExampleBulkReviewResponse(updated=len(examples))


@router.post("/{dataset_id}/split", response_model=DatasetSplitResponse)
def split_dataset(
    dataset_id: int,
    payload: DatasetSplitRequest,
    db: DbSession = Depends(get_db),
) -> DatasetSplitResponse:
    dataset = get_dataset_or_404(db, dataset_id)
    assignments = apply_dataset_split(
        db,
        dataset,
        train_ratio=payload.train_ratio,
        dev_ratio=payload.dev_ratio,
        test_ratio=payload.test_ratio,
        stratify_by=payload.stratify_by,
        include_needs_review=payload.include_needs_review,
    )
    return DatasetSplitResponse(assignments=assignments, quality_summary_json=dataset.quality_summary_json)


@router.get("/{dataset_id}/quality-report", response_model=DatasetQualityReportResponse)
def get_dataset_quality_report(dataset_id: int, db: DbSession = Depends(get_db)) -> DatasetQualityReportResponse:
    dataset = get_dataset_or_404(db, dataset_id)
    refresh_dataset_quality_summary(db, dataset)
    db.commit()
    db.refresh(dataset)
    return DatasetQualityReportResponse(dataset_id=dataset.id, quality_summary_json=dataset.quality_summary_json)
