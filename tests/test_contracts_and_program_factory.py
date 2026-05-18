"""任务契约与 DSPy 程序工厂回归测试。"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import dspy
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.models.dataset import DatasetExample
from backend.services.dspy_program_factory import to_dspy_example
from backend.services.optimization_service import build_optimizer_metric, resolve_metric_threshold
from backend.services.validators import validate_prompt_template, validate_task_contract_alignment


def test_validate_prompt_template_accepts_multi_field_variables() -> None:
    """提示词模板应允许引用输入 schema 中声明的多个字段。"""
    variables, warnings = validate_prompt_template(
        "Question: {question}\nContext: {context}",
        {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "context": {"type": "string"},
            },
            "required": ["question", "context"],
        },
    )

    assert variables == ["context", "question"]
    assert warnings == []


def test_validate_task_contract_alignment_rejects_unsupported_input_field_type() -> None:
    """多字段 signature 这轮只支持标量输入字段。"""
    with pytest.raises(Exception) as exc_info:
        validate_task_contract_alignment(
            {
                "task_key": "multi_modal",
                "input_schema_json": {
                    "type": "object",
                    "properties": {"items": {"type": "array", "items": {"type": "string"}}},
                },
                "output_schema_json": {
                    "type": "object",
                    "properties": {"answer": {"type": "string"}},
                    "required": ["answer"],
                },
                "default_metric_config_json": {"metric": "json_field_accuracy", "field": "answer"},
                "task_definition_json": {"target_field": "answer"},
                "report_profile_json": {
                    "primary_output_field": "answer",
                    "focus_areas": ["accuracy"],
                },
            },
            task_kind="custom",
        )
    assert "input schema field 'items'" in str(exc_info.value)


def test_to_dspy_example_preserves_raw_input_and_multi_field_inputs() -> None:
    """DSPy Example 应同时保留结构化输入和渲染后的文本。"""
    example = DatasetExample(
        id=7,
        dataset_id=1,
        split="test",
        input_json={"question": "When was DSPy released?", "context": "The paper was announced in 2024."},
        expected_output_json={"answer": "2024"},
        metadata_json={},
        content_hash="abc",
    )
    dsp_example = to_dspy_example(
        example,
        {
            "user_template": "Question: {question}\nContext: {context}",
            "input_schema_json": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "context": {"type": "string"},
                },
                "required": ["question", "context"],
            },
            "output_schema_json": {
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
            },
        },
    )

    assert dsp_example.inputs().toDict() == {
        "question": "When was DSPy released?",
        "context": "The paper was announced in 2024.",
    }
    assert dsp_example.raw_input_json == example.input_json
    assert "Question: When was DSPy released?" in dsp_example.rendered_input_text
    assert "Context: The paper was announced in 2024." in dsp_example.rendered_input_text


def test_optimizer_metric_returns_continuous_score_and_threshold() -> None:
    """非 GEPA 优化器应直接消费连续 score。"""
    gold = dspy.Example(
        question="What year?",
        expected_output_json={"answer": "2024"},
        raw_input_json={"question": "What year?"},
        rendered_input_text="What year?",
    ).with_inputs("question")
    pred = SimpleNamespace(answer='{"answer": "2024"}')

    metric = build_optimizer_metric(
        "f1_token",
        "answer",
        output_schema_json={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
        },
        metric_config={"correct_threshold": 0.8},
        feedback=False,
    )

    assert metric(gold, pred) == 1.0
    assert resolve_metric_threshold({"correct_threshold": 0.8}) == 0.8
