"""DSPy 程序与数据集构建工厂。

负责将提示词快照转换为 DSPy 可执行 Module，并将数据集样本转换为 DSPy Example。
"""

import json
from dataclasses import dataclass
from typing import Any

import dspy

from backend.core.exceptions import bad_request
from backend.models.dataset import DatasetExample
from backend.services.validators import get_required_input_fields, get_signature_input_fields


@dataclass
class DSPyDatasetBundle:
    """DSPy 数据集分捆容器，包含训练集、验证集、测试集和全部样本。"""

    trainset: list[dspy.Example]
    devset: list[dspy.Example]
    testset: list[dspy.Example]
    all_examples: list[dspy.Example]


class PromptOptimizationProgram(dspy.Module):
    """基于 DSPy 的提示词优化预测模块。"""

    def __init__(self, instructions: str, user_template: str, input_fields: list[str]):
        super().__init__()
        self.user_template = user_template
        self.input_fields = input_fields
        signature = dspy.Signature("rendered_prompt -> answer", instructions=instructions)
        self.predict = dspy.Predict(signature)

    def forward(self, **inputs: Any):
        """接收结构化输入字段，内部渲染为文本提示后执行预测。"""
        rendered_prompt = render_user_text(
            self.user_template,
            {field_name: inputs.get(field_name) for field_name in self.input_fields},
        )
        return self.predict(rendered_prompt=rendered_prompt)


def build_program(prompt_snapshot_json: dict[str, Any]) -> PromptOptimizationProgram:
    """根据提示词快照构建 DSPy 预测程序。"""
    instructions = build_instructions(prompt_snapshot_json)
    input_fields = get_signature_input_fields(prompt_snapshot_json.get("input_schema_json") or {})
    return PromptOptimizationProgram(
        instructions=instructions,
        user_template=prompt_snapshot_json.get("user_template") or "{text}",
        input_fields=input_fields,
    )


def build_instructions(prompt_snapshot_json: dict[str, Any]) -> str:
    """从提示词快照中拼接完整的指令文本。"""
    system_prompt = (prompt_snapshot_json.get("system_prompt") or "").strip()
    user_template = (prompt_snapshot_json.get("user_template") or "{text}").strip()
    input_schema_json = prompt_snapshot_json.get("input_schema_json") or {}
    output_schema_json = prompt_snapshot_json.get("output_schema_json") or {}
    input_schema_text = json.dumps(input_schema_json, ensure_ascii=False, indent=2)
    output_schema_text = json.dumps(output_schema_json, ensure_ascii=False, indent=2)
    schema_type = output_schema_json.get("type")
    output_instruction = (
        "Return the answer as raw JSON that exactly matches the output schema above."
        if schema_type == "object"
        else "Return the final answer as raw text only, without markdown fences or explanations."
    )
    parts = [
        "You are executing a prompt optimization task.",
        "The caller will provide structured input fields that must be rendered with the user template.",
        f"System prompt:\n{system_prompt}" if system_prompt else "System prompt: <empty>",
        f"Input schema:\n{input_schema_text}",
        f"User template:\n{user_template}",
        f"Output schema:\n{output_schema_text}",
        output_instruction,
    ]
    return "\n\n".join(parts)


def build_dataset_bundle(
    examples: list[DatasetExample],
    prompt_snapshot_json: dict[str, Any],
) -> DSPyDatasetBundle:
    """将样本列表转换为按划分分捆的 DSPy Example 集合。"""
    converted = [to_dspy_example(example, prompt_snapshot_json) for example in examples]
    trainset = [example for example in converted if example.split == "train"]
    devset = [example for example in converted if example.split == "dev"]
    testset = [example for example in converted if example.split == "test"]
    if not testset:
        fallback = devset or trainset
        testset = list(fallback)
    return DSPyDatasetBundle(
        trainset=trainset,
        devset=devset,
        testset=testset,
        all_examples=converted,
    )


def to_dspy_example(example: DatasetExample, prompt_snapshot_json: dict[str, Any]) -> dspy.Example:
    """将单条样本转换为 DSPy Example 对象。"""
    input_schema_json = prompt_snapshot_json.get("input_schema_json") or {}
    input_fields = get_signature_input_fields(input_schema_json)
    required_fields = get_required_input_fields(input_schema_json)
    input_payload = normalize_input_payload(
        example.input_json,
        input_fields=input_fields,
        required_fields=required_fields,
        example_id=example.id,
    )
    rendered_text = render_user_text(
        prompt_snapshot_json.get("user_template") or "{text}",
        input_payload,
    )
    answer = stringify_expected_output(
        prompt_snapshot_json.get("output_schema_json") or {},
        example.expected_output_json,
    )
    return dspy.Example(
        **input_payload,
        answer=answer,
        expected_output_json=example.expected_output_json,
        raw_input_json=example.input_json,
        rendered_input_text=rendered_text,
        example_id=example.id,
        split=example.split,
    ).with_inputs(*input_fields)


def normalize_input_payload(
    input_json: dict[str, Any],
    *,
    input_fields: list[str],
    required_fields: set[str],
    example_id: int | None = None,
) -> dict[str, Any]:
    """根据输入字段列表规范化样本输入。"""
    payload: dict[str, Any] = {}
    missing_required = [field_name for field_name in required_fields if field_name not in input_json]
    if missing_required:
        joined = ", ".join(sorted(missing_required))
        prefix = f"example {example_id} " if example_id is not None else ""
        raise bad_request(f"{prefix}is missing required input fields: {joined}")

    for field_name in input_fields:
        payload[field_name] = input_json.get(field_name, "")
    return payload


def render_user_text(user_template: str, input_json: dict[str, Any]) -> str:
    """使用输入数据渲染用户模板中的占位变量。"""
    rendered = user_template
    for key, value in input_json.items():
        rendered = rendered.replace(f"{{{key}}}", stringify_prompt_value(value))
    return rendered


def stringify_prompt_value(value: Any) -> str:
    """将输入字段值序列化为可嵌入模板的文本。"""
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def stringify_expected_output(
    output_schema_json: dict[str, Any],
    expected_output_json: dict[str, Any],
) -> str:
    """将期望输出序列化为字符串。"""
    schema_type = output_schema_json.get("type")
    if (
        schema_type == "string"
        and isinstance(expected_output_json, dict)
        and "answer" in expected_output_json
    ):
        return str(expected_output_json["answer"])
    return json.dumps(expected_output_json, ensure_ascii=False, sort_keys=True)


def parse_prediction_output(output_schema_json: dict[str, Any], answer: str) -> dict[str, Any]:
    """将模型原始输出解析为结构化字典。"""
    schema_type = output_schema_json.get("type")
    if schema_type == "string":
        return {"answer": answer.strip()}

    try:
        parsed = json.loads(answer)
        if isinstance(parsed, dict):
            return parsed
        return {
            "answer": parsed,
            "__meta__": {"error_type": "schema_error", "raw_answer": answer},
        }
    except (json.JSONDecodeError, ValueError):
        return {
            "answer": answer.strip(),
            "__meta__": {"error_type": "parse_error", "raw_answer": answer},
        }


def strip_internal_prediction_fields(prediction: dict[str, Any]) -> dict[str, Any]:
    """移除预测结果中以 __ 开头的内部字段。"""
    return {key: value for key, value in prediction.items() if not key.startswith("__")}


def extract_predictor_demos(program: dspy.Module) -> list[dict[str, Any]]:
    """从 DSPy Module 中提取所有预测器的 few-shot 示例。"""
    demos: list[dict[str, Any]] = []
    for name, predictor in program.named_predictors():
        for demo in getattr(predictor, "demos", []):
            demos.append(
                {
                    "predictor": name,
                    "rendered_prompt": getattr(demo, "rendered_prompt", None),
                    "answer": getattr(demo, "answer", None),
                }
            )
    return demos


def dump_program_state(program: dspy.Module) -> dict[str, Any]:
    """导出 DSPy Module 的完整状态，包括类型、内部状态和示例。"""
    return {
        "module_type": type(program).__name__,
        "state": program.dump_state(),
        "demos": extract_predictor_demos(program),
    }
