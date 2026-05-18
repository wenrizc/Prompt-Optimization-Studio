"""数据集生成与拆分回归测试。"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.base import Base
from backend.models.dataset import Dataset, DatasetExample
from backend.models.project import Project
from backend.services import dataset_generation, dataset_service


def _build_project() -> Project:
    """构造测试用项目对象。"""
    return Project(
        name="history-facts",
        description="历史事实问答",
        task_kind="builtin",
        task_key="qa",
        task_display_name="历史事实问答",
        task_description="根据问题返回事实答案",
        input_schema_json={"type": "object", "properties": {"text": {"type": "string"}}},
        output_schema_json={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
        },
        default_metric_config_json={},
        task_definition_json={},
        report_profile_json={},
        status="active",
    )


def _build_session() -> Session:
    """创建测试用内存数据库会话。"""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_local()


def test_generate_openai_examples_retries_until_requested_count(monkeypatch) -> None:
    """当单次 LLM 返回不足时，生成逻辑应自动补齐到请求数量。"""
    project = _build_project()
    requested_batch_sizes: list[int] = []

    def fake_generate_structured(
        *,
        model: str,
        instructions: str,
        input_text: str,
        text_format: type,
        **_: object,
    ) -> object:
        del model, instructions
        count_line = next(
            line for line in input_text.splitlines() if line.startswith("Count: ")
        )
        requested = int(count_line.split(": ", 1)[1])
        requested_batch_sizes.append(requested)

        returned = 3 if len(requested_batch_sizes) == 1 else requested
        items = [
            {
                "input": {"text": f"question-{len(requested_batch_sizes)}-{index}"},
                "expected_output": {"answer": f"answer-{index}"},
            }
            for index in range(1, returned + 1)
        ]
        return text_format.model_validate({"items": items})

    monkeypatch.setattr(
        dataset_generation.openai_client_service,
        "generate_structured",
        fake_generate_structured,
    )

    examples = dataset_generation.generate_openai_examples(
        project=project,
        command="生成历史事实问答",
        count=12,
        generation_model="deepseek-v4-pro",
    )

    assert len(examples) == 12
    assert requested_batch_sizes == [10, 9]
    assert examples[0]["metadata_json"]["generation_model"] == "deepseek-v4-pro"


def test_apply_dataset_split_disables_bad_auto_stratification_for_open_qa() -> None:
    """开放式问答答案高基数时，不应误用自动分层导致拆分失衡。"""
    session = _build_session()
    project = _build_project()
    session.add(project)
    session.flush()

    dataset = Dataset(
        project_id=project.id,
        name="history-dataset",
        source_type="synthetic_generated",
        schema_json=project.input_schema_json,
        quality_summary_json={},
        status="active",
    )
    session.add(dataset)
    session.flush()

    examples = [
        {
            "input_json": {"text": f"问题 {index}"},
            "expected_output_json": {"answer": f"独特答案 {index}"},
            "metadata_json": {"source": "synthetic_generated"},
        }
        for index in range(1, 51)
    ]
    dataset_service.import_dataset_examples(session, dataset, examples)

    assignments = dataset_service.apply_dataset_split(
        session,
        dataset,
        train_ratio=0.6,
        dev_ratio=0.2,
        test_ratio=0.2,
    )

    split_counts = Counter(
        session.scalars(
            select(DatasetExample.split).where(DatasetExample.dataset_id == dataset.id)
        )
    )

    assert assignments == {"train": 30, "dev": 10, "test": 10}
    assert split_counts == Counter({"train": 30, "dev": 10, "test": 10})
    assert dataset.quality_summary_json["split_counts"] == {"train": 30, "dev": 10, "test": 10}


def test_parse_import_content_maps_scalar_to_single_output_field() -> None:
    """单字段 object 输出应把 scalar 自动映射到真实字段名。"""
    rows = dataset_service.parse_import_content(
        content='[{"utterance":"需要退款","label":"refund"}]',
        file_format="json",
        input_field="utterance",
        output_field="label",
        input_schema_json={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        output_schema_json={
            "type": "object",
            "properties": {"label": {"type": "string"}},
            "required": ["label"],
        },
    )

    assert rows == [
        {
            "input_json": {"text": "需要退款"},
            "expected_output_json": {"label": "refund"},
            "metadata_json": {},
        }
    ]


def test_parse_import_content_rejects_scalar_for_multi_field_output() -> None:
    """多字段 object 输出不允许用 scalar 进行猜测性映射。"""
    with pytest.raises(Exception) as exc_info:
        dataset_service.parse_import_content(
            content='[{"text":"样本","expected_output":"fallback"}]',
            file_format="json",
            input_field="text",
            output_field="expected_output",
            input_schema_json={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            output_schema_json={
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["label"],
            },
        )
    assert "scalar output rows can only be imported" in str(exc_info.value)


def test_generate_mock_examples_keeps_metadata_shape_for_multi_field_input() -> None:
    """mock synthetic 数据应统一 metadata 字段，并支持多字段输入。"""
    project = Project(
        name="triage",
        description="工单分流",
        task_kind="custom",
        task_key="ticket_triage",
        task_display_name="工单分流",
        task_description="根据标题和正文分类",
        input_schema_json={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["title", "body"],
        },
        output_schema_json={
            "type": "object",
            "properties": {"label": {"type": "string"}},
            "required": ["label"],
        },
        default_metric_config_json={},
        task_definition_json={},
        report_profile_json={},
        status="active",
    )

    examples = dataset_generation.generate_mock_examples(project, "生成工单", 2)

    assert set(examples[0]["input_json"]) == {"title", "body"}
    assert examples[0]["metadata_json"] == {
        "source": "synthetic_generated",
        "command": "生成工单",
        "generation_model": "mock",
        "batch_index": 1,
        "generation_mode": "mock",
    }
