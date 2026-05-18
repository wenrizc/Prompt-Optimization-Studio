"""数据集管理与导入服务。

提供数据集导入解析、样本管理、质量统计和数据集划分等功能。
"""

import csv
import json
import random
from collections import Counter, defaultdict
from io import StringIO
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.exceptions import bad_request, not_found
from backend.models.dataset import Dataset, DatasetExample
from backend.services.validators import (
    compute_example_content_hash,
    get_signature_input_fields,
)

COMMON_LABEL_FIELDS = ("label", "category", "class", "intent", "answer")


def parse_import_content(
    content: str,
    file_format: str,
    input_field: str,
    output_field: str,
    metadata_fields: list[str] | None = None,
    input_schema_json: dict[str, Any] | None = None,
    output_schema_json: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """解析导入文件内容为标准化的样本列表。

    Args:
        content: 文件原始内容。
        file_format: 文件格式, 支持 json、jsonl 或 csv。
        input_field: 输入字段名。
        output_field: 输出字段名。
        metadata_fields: 需要提取的元数据字段列表。
        input_schema_json: 项目输入 schema。
        output_schema_json: 项目输出 schema。

    Returns:
        标准化后的样本字典列表。
    """
    metadata_fields = metadata_fields or []
    input_schema_json = input_schema_json or {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }
    output_schema_json = output_schema_json or {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
    }
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
                "input_json": _normalize_input_row(
                    row,
                    input_field=input_field,
                    input_schema_json=input_schema_json,
                ),
                "expected_output_json": _normalize_output(
                    row[output_field],
                    output_schema_json=output_schema_json,
                ),
                "metadata_json": metadata,
            }
        )
    return normalized_rows


def import_dataset_examples(
    db: Session,
    dataset: Dataset,
    examples: list[dict[str, Any]],
    split: str = "unassigned",
) -> list[DatasetExample]:
    """批量导入样本到数据集中。

    Args:
        db: 数据库会话。
        dataset: 目标数据集。
        examples: 样本字典列表。
        split: 初始划分标签。
    Returns:
        创建的 DatasetExample 列表。
    """
    created: list[DatasetExample] = []
    for example in examples:
        db_example = DatasetExample(
            dataset_id=dataset.id,
            split=split,
            input_json=example["input_json"],
            expected_output_json=example["expected_output_json"],
            metadata_json=example.get("metadata_json", {}),
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
    """重新计算并更新数据集的质量统计摘要。

    Args:
        db: 数据库会话。
        dataset: 目标数据集。

    Returns:
        更新后的质量统计字典。
    """
    examples = list(
        db.scalars(
            select(DatasetExample)
            .where(DatasetExample.dataset_id == dataset.id)
            .order_by(DatasetExample.id.asc())
        )
    )
    summary = build_quality_summary(dataset, examples)
    dataset.quality_summary_json = summary
    db.add(dataset)
    db.flush()
    return summary


def build_quality_summary(dataset: Dataset, examples: list[DatasetExample]) -> dict[str, Any]:
    """构建数据集质量统计摘要, 包含划分分布、重复检测和警告信息。

    Args:
        dataset: 目标数据集。
        examples: 数据集中的所有样本。

    Returns:
        包含统计指标和警告的字典。
    """
    split_counts = Counter(example.split for example in examples)
    source_counts = Counter(
        str(example.metadata_json.get("source", dataset.source_type)) for example in examples
    )
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
    synthetic_count = source_counts.get("synthetic_generated", 0)
    total_count = len(examples)
    real_data_count = total_count - synthetic_count
    trust_level = "high" if real_data_count > 0 else "low"

    if not examples:
        warnings.append("Dataset has no examples")
    if split_counts.get("test", 0) == 0:
        warnings.append("Dataset has no test split examples")
    if 0 < split_counts.get("test", 0) < 10:
        warnings.append("Test split has fewer than 10 examples; confidence will be low")
    if 0 < total_count < 10:
        warnings.append(
            "Dataset has fewer than 10 examples; only quick experiments are recommended"
        )
    if 0 < total_count < 30:
        warnings.append(
            "Dataset has fewer than 30 examples; MIPROv2 and GEPA should be treated as low-confidence"
        )
    if duplicate_groups:
        warnings.append("Dataset contains duplicate examples")
    if cross_split_duplicates:
        warnings.append("Dataset contains duplicates across splits")
    if synthetic_count == total_count and total_count > 0:
        warnings.append("Dataset is synthetic-only; reported scores are lower-trust")

    return {
        "total_examples": len(examples),
        "split_counts": dict(split_counts),
        "source_counts": dict(source_counts),
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
) -> dict[str, int]:
    """按比例将数据集样本划分为 train/dev/test 子集。

    Args:
        db: 数据库会话。
        dataset: 目标数据集。
        train_ratio: 训练集比例。
        dev_ratio: 验证集比例。
        test_ratio: 测试集比例。
        stratify_by: 分层采样的目标字段名。
    Returns:
        各划分的实际样本数量字典。
    """
    if round(train_ratio + dev_ratio + test_ratio, 6) != 1.0:
        raise bad_request("train_ratio + dev_ratio + test_ratio must equal 1.0")

    all_examples = list(
        db.scalars(
            select(DatasetExample)
            .where(DatasetExample.dataset_id == dataset.id)
            .order_by(DatasetExample.id.asc())
        )
    )
    if not all_examples:
        raise bad_request("dataset has no eligible examples to split")

    group_keys = build_split_group_keys(all_examples, stratify_by)
    blocks_by_group: dict[str, list[list[DatasetExample]]] = defaultdict(list)
    content_blocks: dict[tuple[str, str], list[DatasetExample]] = defaultdict(list)
    for example in all_examples:
        group_key = group_keys[example.id]
        content_blocks[(group_key, example.content_hash)].append(example)

    for (group_key, _content_hash), block in content_blocks.items():
        blocks_by_group[group_key].append(block)

    rng = random.Random(42)
    total_target_counts = allocate_split_counts(len(all_examples), train_ratio, dev_ratio, test_ratio)
    assignments = {"train": 0, "dev": 0, "test": 0}
    for blocks in sorted(blocks_by_group.values(), key=lambda value: sum(len(block) for block in value), reverse=True):
        rng.shuffle(blocks)
        group_size = sum(len(block) for block in blocks)
        target_counts = allocate_split_counts(group_size, train_ratio, dev_ratio, test_ratio)
        group_assignments = {"train": 0, "dev": 0, "test": 0}

        for block in sorted(blocks, key=len, reverse=True):
            split_name = choose_split_for_block(
                block_size=len(block),
                target_counts=target_counts,
                current_counts=group_assignments,
                global_target_counts=total_target_counts,
                global_current_counts=assignments,
            )
            for example in block:
                example.split = split_name
                db.add(example)
                assignments[split_name] += 1
                group_assignments[split_name] += 1

    refresh_dataset_quality_summary(db, dataset)
    db.commit()
    db.refresh(dataset)
    return assignments


def write_import_snapshot(dataset_id: int, file_format: str, content: str) -> str:
    """将导入文件内容持久化到磁盘。

    Args:
        dataset_id: 数据集主键。
        file_format: 文件格式后缀。
        content: 文件原始内容。

    Returns:
        文件相对路径。
    """
    settings = get_settings()
    target_dir = settings.uploads_dir / f"dataset_{dataset_id}"
    target_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"import.{file_format}"
    target_path = target_dir / file_name
    target_path.write_text(content, encoding="utf-8")
    return str(Path("uploads") / f"dataset_{dataset_id}" / file_name)


def get_dataset_or_404(db: Session, dataset_id: int) -> Dataset:
    """获取数据集, 不存在时抛出 404 异常。"""
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise not_found(f"Dataset {dataset_id} not found")
    return dataset


def detect_label(expected_output_json: dict[str, Any]) -> str | None:
    """从期望输出中检测标签值, 用于分层采样。"""
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
    """确定样本的分组键, 用于分层划分。"""
    if stratify_by:
        value = example.expected_output_json.get(stratify_by)
        if value is not None:
            return str(value)
    label = detect_label(example.expected_output_json)
    if label is not None:
        return label
    return "_default"


def build_split_group_keys(
    examples: list[DatasetExample], stratify_by: str | None
) -> dict[int, str]:
    """为样本构建拆分分组键。

    默认只在标签分布明显呈现低基数分类任务时自动分层，避免把开放式问答答案
    误判为分类标签，导致几乎所有样本都落到训练集。
    """
    if stratify_by:
        return {example.id: determine_group_key(example, stratify_by) for example in examples}
    if not should_auto_stratify(examples):
        return {example.id: "_default" for example in examples}
    return {example.id: determine_group_key(example, None) for example in examples}


def should_auto_stratify(examples: list[DatasetExample]) -> bool:
    """判断当前数据集是否适合基于自动检测标签进行分层拆分。"""
    labels = [detect_label(example.expected_output_json) for example in examples]
    valid_labels = [label for label in labels if label is not None]
    if len(valid_labels) < 2:
        return False

    label_counts = Counter(valid_labels)
    unique_label_count = len(label_counts)
    repeated_example_count = sum(count for count in label_counts.values() if count > 1)
    total_count = len(examples)

    if unique_label_count > max(20, total_count // 2):
        return False
    return repeated_example_count >= max(2, total_count // 3)


def allocate_split_counts(
    group_size: int, train_ratio: float, dev_ratio: float, test_ratio: float
) -> dict[str, int]:
    """按比例分配各划分的目标样本数量。

    Args:
        group_size: 当前分组样本总数。
        train_ratio: 训练集比例。
        dev_ratio: 验证集比例。
        test_ratio: 测试集比例。

    Returns:
        各划分的实际数量字典。
    """
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

    non_zero = [
        name
        for name, ratio in {"train": train_ratio, "dev": dev_ratio, "test": test_ratio}.items()
        if ratio > 0
    ]
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
    global_target_counts: dict[str, int] | None = None,
    global_current_counts: dict[str, int] | None = None,
) -> str:
    """为内容块选择最合适的划分, 尽量保持比例均衡。

    Args:
        block_size: 内容块大小。
        target_counts: 各划分目标数量。
        current_counts: 各划分当前已分配数量。

    Returns:
        选中的划分名称。
    """
    candidate_splits = sorted(
        target_counts.keys(),
        key=lambda split: (
            _remaining_capacity(global_target_counts, global_current_counts, split),
            target_counts[split] - current_counts[split],
            -current_counts[split],
        ),
        reverse=True,
    )
    for split_name in candidate_splits:
        group_limit = max(target_counts[split_name], block_size)
        global_limit = max(
            _target_value(global_target_counts, split_name),
            block_size,
        )
        if current_counts[split_name] + block_size > group_limit:
            continue
        if _current_value(global_current_counts, split_name) + block_size > global_limit:
            continue
        return split_name

    for split_name in candidate_splits:
        if current_counts[split_name] + block_size <= max(target_counts[split_name], block_size):
            return split_name
    return candidate_splits[0]


def _remaining_capacity(
    target_counts: dict[str, int] | None,
    current_counts: dict[str, int] | None,
    split_name: str,
) -> int:
    """计算指定 split 的剩余容量。"""
    return _target_value(target_counts, split_name) - _current_value(current_counts, split_name)


def _target_value(target_counts: dict[str, int] | None, split_name: str) -> int:
    """读取目标数量，空值时返回 0。"""
    if target_counts is None:
        return 0
    return target_counts.get(split_name, 0)


def _current_value(current_counts: dict[str, int] | None, split_name: str) -> int:
    """读取当前数量，空值时返回 0。"""
    if current_counts is None:
        return 0
    return current_counts.get(split_name, 0)


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


def _normalize_input_row(
    row: dict[str, Any],
    *,
    input_field: str,
    input_schema_json: dict[str, Any],
) -> dict[str, Any]:
    input_fields = get_signature_input_fields(input_schema_json)
    if len(input_fields) == 1:
        return {input_fields[0]: row[input_field]}

    missing_fields = [field_name for field_name in input_fields if field_name not in row]
    if missing_fields:
        joined = ", ".join(missing_fields)
        raise bad_request(f"row is missing multi-field input columns: {joined}")
    return {field_name: row[field_name] for field_name in input_fields}


def _normalize_output(value: Any, *, output_schema_json: dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value

    schema_type = output_schema_json.get("type")
    if schema_type == "string":
        return {"answer": value}

    properties = output_schema_json.get("properties") or {}
    if len(properties) == 1:
        target_field = next(iter(properties))
        return {target_field: value}
    raise bad_request(
        "scalar output rows can only be imported when output schema is string "
        "or an object with exactly one field"
    )
