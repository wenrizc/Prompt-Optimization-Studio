import csv
import json
import random
from collections import Counter, defaultdict
from io import StringIO
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from prompt_optimization_studio.core.config import get_settings
from prompt_optimization_studio.core.exceptions import bad_request, not_found
from prompt_optimization_studio.models.dataset import Dataset, DatasetExample
from prompt_optimization_studio.services.validators import compute_example_content_hash

COMMON_LABEL_FIELDS = ("label", "category", "class", "intent", "answer")


def parse_import_content(
    content: str,
    file_format: str,
    input_field: str,
    output_field: str,
    metadata_fields: list[str] | None = None,
) -> list[dict[str, Any]]:
    metadata_fields = metadata_fields or []
    if not content.strip():
        raise bad_request("import content cannot be empty")

    if file_format == "json":
        rows = _parse_json_rows(content)
    elif file_format == "jsonl":
        rows = _parse_jsonl_rows(content)
    elif file_format == "csv":
        rows = _parse_csv_rows(content)
    else:
        raise bad_request("unsupported import format; use json, jsonl, or csv")

    normalized_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        if input_field not in row:
            raise bad_request(f"row {index} is missing input field '{input_field}'")
        if output_field not in row:
            raise bad_request(f"row {index} is missing output field '{output_field}'")

        metadata = {field: row[field] for field in metadata_fields if field in row}
        normalized_rows.append(
            {
                "input_json": {"text": str(row[input_field])},
                "expected_output_json": _normalize_output(row[output_field]),
                "metadata_json": metadata,
            }
        )
    return normalized_rows


def import_dataset_examples(
    db: Session,
    dataset: Dataset,
    examples: list[dict[str, Any]],
    split: str = "unassigned",
    quality_status: str = "unchecked",
) -> list[DatasetExample]:
    created: list[DatasetExample] = []
    for example in examples:
        db_example = DatasetExample(
            dataset_id=dataset.id,
            split=split,
            input_json=example["input_json"],
            expected_output_json=example["expected_output_json"],
            metadata_json=example.get("metadata_json", {}),
            quality_status=quality_status,
            content_hash=compute_example_content_hash(
                example["input_json"],
                example["expected_output_json"],
            ),
        )
        db.add(db_example)
        created.append(db_example)

    db.flush()
    refresh_dataset_quality_summary(db, dataset)
    db.commit()
    for item in created:
        db.refresh(item)
    db.refresh(dataset)
    return created


def refresh_dataset_quality_summary(db: Session, dataset: Dataset) -> dict[str, Any]:
    examples = list(
        db.scalars(
            select(DatasetExample).where(DatasetExample.dataset_id == dataset.id).order_by(DatasetExample.id.asc())
        )
    )
    summary = build_quality_summary(dataset, examples)
    dataset.quality_summary_json = summary
    db.add(dataset)
    db.flush()
    return summary


def build_quality_summary(dataset: Dataset, examples: list[DatasetExample]) -> dict[str, Any]:
    split_counts = Counter(example.split for example in examples)
    quality_counts = Counter(example.quality_status for example in examples)
    source_counts = Counter(str(example.metadata_json.get("source", dataset.source_type)) for example in examples)
    label_counts = Counter()
    content_groups: dict[str, list[int]] = defaultdict(list)
    hash_split_groups: dict[str, set[str]] = defaultdict(set)

    for example in examples:
        content_groups[example.content_hash].append(example.id)
        hash_split_groups[example.content_hash].add(example.split)
        label = detect_label(example.expected_output_json)
        if label is not None:
            label_counts[label] += 1

    duplicate_groups = [ids for ids in content_groups.values() if len(ids) > 1]
    cross_split_duplicates = [
        {
            "content_hash": content_hash,
            "example_ids": content_groups[content_hash],
            "splits": sorted(splits),
        }
        for content_hash, splits in hash_split_groups.items()
        if len(splits - {"unassigned"}) > 1
    ]

    warnings: list[str] = []
    reviewed_count = quality_counts.get("accepted", 0)
    synthetic_count = source_counts.get("synthetic_generated", 0)
    total_count = len(examples)
    real_data_count = total_count - synthetic_count
    trust_level = "low"
    if real_data_count > 0:
        trust_level = "high"
    elif synthetic_count > 0 and reviewed_count > 0:
        trust_level = "medium"

    if not examples:
        warnings.append("Dataset has no examples")
    if split_counts.get("test", 0) == 0:
        warnings.append("Dataset has no test split examples")
    if 0 < split_counts.get("test", 0) < 10:
        warnings.append("Test split has fewer than 10 examples; confidence will be low")
    if 0 < total_count < 10:
        warnings.append("Dataset has fewer than 10 examples; only quick experiments are recommended")
    if 0 < total_count < 30:
        warnings.append("Dataset has fewer than 30 examples; MIPROv2 and GEPA should be treated as low-confidence")
    if quality_counts.get("unchecked", 0) > 0:
        warnings.append("Dataset contains unchecked examples")
    if duplicate_groups:
        warnings.append("Dataset contains duplicate examples")
    if cross_split_duplicates:
        warnings.append("Dataset contains duplicates across splits")
    if synthetic_count == total_count and total_count > 0:
        warnings.append("Dataset is synthetic-only; reported scores are lower-trust")

    synthetic_test_unchecked = any(
        example.split == "test"
        and str(example.metadata_json.get("source", dataset.source_type)) == "synthetic_generated"
        and example.quality_status == "unchecked"
        for example in examples
    )
    if synthetic_test_unchecked:
        warnings.append("Test split is synthetic and unchecked; final conclusions should be treated as low-confidence")

    return {
        "total_examples": len(examples),
        "split_counts": dict(split_counts),
        "quality_counts": dict(quality_counts),
        "source_counts": dict(source_counts),
        "reviewed_example_count": reviewed_count,
        "synthetic_example_count": synthetic_count,
        "real_example_count": real_data_count,
        "trust_level": trust_level,
        "label_distribution": dict(label_counts),
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_example_count": sum(len(group) for group in duplicate_groups),
        "cross_split_duplicate_count": len(cross_split_duplicates),
        "cross_split_duplicates": cross_split_duplicates[:20],
        "warnings": warnings,
    }


def apply_dataset_split(
    db: Session,
    dataset: Dataset,
    train_ratio: float,
    dev_ratio: float,
    test_ratio: float,
    stratify_by: str | None = None,
    include_needs_review: bool = False,
) -> dict[str, int]:
    if round(train_ratio + dev_ratio + test_ratio, 6) != 1.0:
        raise bad_request("train_ratio + dev_ratio + test_ratio must equal 1.0")

    all_examples = list(
        db.scalars(select(DatasetExample).where(DatasetExample.dataset_id == dataset.id).order_by(DatasetExample.id.asc()))
    )
    eligible_examples = [
        example
        for example in all_examples
        if example.quality_status != "rejected"
        and (include_needs_review or example.quality_status != "needs_review")
    ]
    if not eligible_examples:
        raise bad_request("dataset has no eligible examples to split")

    blocks_by_group: dict[str, list[list[DatasetExample]]] = defaultdict(list)
    content_blocks: dict[tuple[str, str], list[DatasetExample]] = defaultdict(list)
    for example in eligible_examples:
        group_key = determine_group_key(example, stratify_by)
        content_blocks[(group_key, example.content_hash)].append(example)

    for (group_key, _content_hash), block in content_blocks.items():
        blocks_by_group[group_key].append(block)

    rng = random.Random(42)
    assignments = {"train": 0, "dev": 0, "test": 0}
    eligible_ids = {example.id for example in eligible_examples}
    for blocks in blocks_by_group.values():
        rng.shuffle(blocks)
        group_size = sum(len(block) for block in blocks)
        target_counts = allocate_split_counts(group_size, train_ratio, dev_ratio, test_ratio)
        group_assignments = {"train": 0, "dev": 0, "test": 0}

        for block in sorted(blocks, key=len, reverse=True):
            split_name = choose_split_for_block(len(block), target_counts, group_assignments)
            for example in block:
                example.split = split_name
                db.add(example)
                assignments[split_name] += 1
                group_assignments[split_name] += 1

    for example in all_examples:
        if example.id not in eligible_ids:
            example.split = "unassigned"
            db.add(example)

    refresh_dataset_quality_summary(db, dataset)
    db.commit()
    db.refresh(dataset)
    return assignments


def write_import_snapshot(dataset_id: int, file_format: str, content: str) -> str:
    settings = get_settings()
    target_dir = settings.uploads_dir / f"dataset_{dataset_id}"
    target_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"import.{file_format}"
    target_path = target_dir / file_name
    target_path.write_text(content, encoding="utf-8")
    return str(Path("uploads") / f"dataset_{dataset_id}" / file_name)


def get_dataset_or_404(db: Session, dataset_id: int) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise not_found(f"Dataset {dataset_id} not found")
    return dataset


def detect_label(expected_output_json: dict[str, Any]) -> str | None:
    if not isinstance(expected_output_json, dict):
        return None
    for field in COMMON_LABEL_FIELDS:
        value = expected_output_json.get(field)
        if isinstance(value, (str, int, float, bool)):
            return str(value)
    if len(expected_output_json) == 1:
        only_value = next(iter(expected_output_json.values()))
        if isinstance(only_value, (str, int, float, bool)):
            return str(only_value)
    return None


def determine_group_key(example: DatasetExample, stratify_by: str | None) -> str:
    if stratify_by:
        value = example.expected_output_json.get(stratify_by)
        if value is not None:
            return str(value)
    label = detect_label(example.expected_output_json)
    if label is not None:
        return label
    return "_default"


def allocate_split_counts(group_size: int, train_ratio: float, dev_ratio: float, test_ratio: float) -> dict[str, int]:
    raw_counts = {
        "train": group_size * train_ratio,
        "dev": group_size * dev_ratio,
        "test": group_size * test_ratio,
    }
    counts = {split: int(value) for split, value in raw_counts.items()}
    remainder = group_size - sum(counts.values())
    priorities = sorted(raw_counts, key=lambda key: raw_counts[key] - counts[key], reverse=True)
    for split_name in priorities[:remainder]:
        counts[split_name] += 1

    non_zero = [name for name, ratio in {"train": train_ratio, "dev": dev_ratio, "test": test_ratio}.items() if ratio > 0]
    if group_size >= len(non_zero):
        for split_name in non_zero:
            if counts[split_name] == 0:
                donor = max(counts, key=counts.get)
                if counts[donor] > 1:
                    counts[donor] -= 1
                    counts[split_name] += 1
    return counts


def choose_split_for_block(
    block_size: int,
    target_counts: dict[str, int],
    current_counts: dict[str, int],
) -> str:
    candidate_splits = sorted(
        target_counts.keys(),
        key=lambda split: (
            target_counts[split] - current_counts[split],
            -current_counts[split],
        ),
        reverse=True,
    )
    for split_name in candidate_splits:
        if current_counts[split_name] + block_size <= max(target_counts[split_name], block_size):
            return split_name
    return candidate_splits[0]


def _parse_json_rows(content: str) -> list[dict[str, Any]]:
    parsed = json.loads(content)
    if not isinstance(parsed, list):
        raise bad_request("json import content must be a list of objects")
    if any(not isinstance(item, dict) for item in parsed):
        raise bad_request("json import rows must all be objects")
    return parsed


def _parse_jsonl_rows(content: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(content.splitlines(), start=1):
        if not line.strip():
            continue
        item = json.loads(line)
        if not isinstance(item, dict):
            raise bad_request(f"jsonl row {index} must be an object")
        rows.append(item)
    return rows


def _parse_csv_rows(content: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(StringIO(content))
    if not reader.fieldnames:
        raise bad_request("csv import content must include a header row")
    return [dict(row) for row in reader]


def _normalize_output(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {"answer": value}
