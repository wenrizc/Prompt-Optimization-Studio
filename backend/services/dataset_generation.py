"""合成数据集生成服务。

支持通过 OpenAI 模型或 Mock 方式批量生成训练数据样本。
"""

import json
from collections.abc import Sequence
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, create_model
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.exceptions import bad_request
from backend.models.dataset import Dataset
from backend.models.project import Project
from backend.services.dataset_service import import_dataset_examples
from backend.services.openai_client import openai_client_service
from backend.services.validators import get_signature_input_fields

StructuredT = TypeVar("StructuredT", bound=BaseModel)


def generate_mock_examples(project: Project, command: str, count: int) -> list[dict[str, Any]]:
    """使用 Mock 策略生成合成样本。"""
    task_key = project.task_key
    output_schema_json = project.output_schema_json or {}
    input_schema_json = project.input_schema_json or {}
    examples: list[dict[str, Any]] = []
    for index in range(1, count + 1):
        input_json = synthesize_input_from_schema(input_schema_json, command, index)
        if task_key == "qa" and "answer" in (output_schema_json.get("properties") or {"answer": {}}):
            expected_output = {"answer": f"问题 {index} 的回答"}
        else:
            expected_output = synthesize_output_from_schema(output_schema_json, index)

        examples.append(
            {
                "input_json": input_json,
                "expected_output_json": expected_output,
                "metadata_json": build_generation_metadata(
                    command=command,
                    generation_model="mock",
                    batch_index=index,
                    generation_mode="mock",
                ),
            }
        )
    return examples


def generate_openai_examples(
    project: Project, command: str, count: int, generation_model: str
) -> list[dict[str, Any]]:
    """使用 OpenAI 模型生成结构化合成样本。"""
    examples: list[dict[str, Any]] = []
    remaining = count
    request_index = 0
    max_attempts = max(3, count * 2)

    while remaining > 0 and request_index < max_attempts:
        batch_count = min(remaining, 10)
        batch_examples = _generate_openai_example_batch(
            project=project,
            command=command,
            count=batch_count,
            generation_model=generation_model,
            request_index=request_index,
        )
        if not batch_examples:
            raise bad_request("LLM returned no dataset examples")

        examples.extend(batch_examples[:batch_count])
        remaining = count - len(examples)
        request_index += 1

    if len(examples) < count:
        raise bad_request(
            f"LLM returned only {len(examples)} examples, fewer than the requested {count}"
        )
    return examples[:count]


def _generate_openai_example_batch(
    project: Project,
    command: str,
    count: int,
    generation_model: str,
    request_index: int,
) -> list[dict[str, Any]]:
    """调用一次结构化 LLM 生成一批合成样本。"""
    input_model = build_input_model(project.input_schema_json or {})
    output_model = build_output_model(project.output_schema_json or {})
    example_model = create_model(
        "SyntheticExampleModel",
        __config__=ConfigDict(extra="forbid"),
        input=(input_model, ...),
        expected_output=(output_model, ...),
    )
    batch_model = create_model(
        "SyntheticBatchModel",
        __config__=ConfigDict(extra="forbid"),
        items=(list[example_model], ...),
    )
    instructions = (
        "Generate synthetic dataset examples for a prompt optimization project. "
        "Match the requested task closely and keep examples realistic, diverse, and concise. "
        "The input field must satisfy the declared input schema exactly. "
        "The expected_output field must satisfy the declared output schema exactly. "
        "Return exactly the requested number of items."
    )
    few_shot = {
        "items": [
            {
                "input": _build_few_shot_input_fields(
                    get_signature_input_fields(project.input_schema_json or {})
                ),
                "expected_output": _build_few_shot_output_fields(
                    project.output_schema_json or {}
                ),
            },
        ]
    }
    input_text = (
        f"Task key: {project.task_key}\n"
        f"Task description: {project.task_description or project.description or ''}\n"
        f"Command: {command}\n"
        f"Batch index: {request_index + 1}\n"
        f"Count: {count}\n"
        f"Input schema: {project.input_schema_json}\n"
        f"Output schema: {project.output_schema_json}\n"
        "Produce varied examples, including short and long phrasing, edge cases, and realistic wording.\n\n"
        'The top-level JSON key MUST be "items" (not "examples" or any other name).\n'
        "Each item must contain an 'input' object and an 'expected_output' value.\n"
        "Example of the required JSON structure:\n"
        f"{json.dumps(few_shot, ensure_ascii=False, indent=2)}"
    )
    parsed = openai_client_service.generate_structured(
        model=generation_model,
        instructions=instructions,
        input_text=input_text,
        text_format=batch_model,
    )
    return [
        {
            "input_json": item.input.model_dump(mode="json"),
            "expected_output_json": normalize_generated_expected_output(
                project.output_schema_json or {},
                item.expected_output,
            ),
            "metadata_json": build_generation_metadata(
                command=command,
                generation_model=generation_model,
                batch_index=request_index + 1,
                generation_mode="openai",
            ),
        }
        for item in parsed.items
    ]


def create_generated_dataset(
    db: Session,
    project: Project,
    name: str,
    command: str,
    count: int,
) -> tuple[Dataset, int]:
    """创建合成数据集并导入生成的样本。"""
    generation_model = resolve_generation_model()
    dataset = Dataset(
        project_id=project.id,
        name=name,
        source_type="synthetic_generated",
        schema_json=project.input_schema_json,
        command=command,
        generation_model=generation_model,
        quality_summary_json={},
        status="active",
    )
    db.add(dataset)
    db.flush()

    if generation_model != "mock" and openai_client_service.configured:
        examples = generate_openai_examples(project, command, count, generation_model)
    else:
        examples = generate_mock_examples(project, command, count)
    created = import_dataset_examples(
        db=db,
        dataset=dataset,
        examples=examples,
        split="unassigned",
    )
    return dataset, len(created)


def resolve_generation_model() -> str:
    """解析当前环境下实际使用的数据生成模型。"""
    if not openai_client_service.configured:
        return "mock"

    generation_model = get_settings().openai_default_model.strip()
    if not generation_model:
        raise bad_request("OPENAI_DEFAULT_MODEL is not configured")
    return generation_model


def build_input_model(input_schema_json: dict[str, Any]) -> type[BaseModel]:
    """根据输入 schema 构建 Pydantic 模型类。"""
    fields: dict[str, tuple[Any, Any]] = {}
    required = set(input_schema_json.get("required", []))
    for field_name, field_schema in (input_schema_json.get("properties") or {}).items():
        annotation = schema_to_annotation(field_schema, suffix=f"{field_name.title()}Input")
        default = ... if field_name in required else None
        fields[field_name] = (annotation, default)
    return create_model("GeneratedInputModel", __config__=ConfigDict(extra="forbid"), **fields)


def build_output_model(output_schema_json: dict[str, Any]) -> type[BaseModel]:
    """根据输出 schema 构建 Pydantic 模型类。"""
    schema_type = output_schema_json.get("type")
    if schema_type == "string":
        return create_model(
            "GeneratedOutputModel",
            __config__=ConfigDict(extra="forbid"),
            answer=(str, ...),
        )

    fields: dict[str, tuple[Any, Any]] = {}
    required = set(output_schema_json.get("required", []))
    for field_name, field_schema in (output_schema_json.get("properties") or {}).items():
        annotation = schema_to_annotation(field_schema, suffix=f"{field_name.title()}Output")
        default = ... if field_name in required else None
        fields[field_name] = (annotation, default)

    if not fields:
        fields["answer"] = (str, ...)

    return create_model("GeneratedOutputModel", __config__=ConfigDict(extra="forbid"), **fields)


def schema_to_annotation(schema: dict[str, Any], *, suffix: str) -> Any:
    """将 JSON Schema 字段定义转换为 Python 类型注解。"""
    schema_type = schema.get("type")
    enum_values = schema.get("enum")
    if enum_values:
        literal_values = tuple(enum_values)
        return Literal.__getitem__(literal_values)
    if schema_type == "string":
        return str
    if schema_type == "integer":
        return int
    if schema_type == "number":
        return float
    if schema_type == "boolean":
        return bool
    if schema_type == "array":
        item_schema = schema.get("items") or {"type": "string"}
        return list[schema_to_annotation(item_schema, suffix=f"{suffix}Item")]
    if schema_type == "object":
        nested_model = build_output_model(schema)
        nested_model.__name__ = f"{suffix}Model"
        return nested_model
    return str


def synthesize_input_from_schema(
    input_schema_json: dict[str, Any],
    command: str,
    index: int,
) -> dict[str, Any]:
    """根据输入 schema 合成 Mock 输入值。"""
    payload: dict[str, Any] = {}
    properties = input_schema_json.get("properties") or {}
    for field_name, field_schema in properties.items():
        if field_name == "text":
            payload[field_name] = f"{command} 示例 {index}"
        else:
            payload[field_name] = synthesize_value(field_schema, index)
    return payload or {"text": f"{command} 示例 {index}"}


def synthesize_output_from_schema(output_schema_json: dict[str, Any], index: int) -> dict[str, Any]:
    """根据输出 schema 合成 Mock 输出值。"""
    schema_type = output_schema_json.get("type")
    if schema_type == "string":
        return {"answer": f"synthetic answer {index}"}

    payload: dict[str, Any] = {}
    for field_name, field_schema in (output_schema_json.get("properties") or {}).items():
        payload[field_name] = synthesize_value(field_schema, index)
    return payload or {"answer": f"synthetic answer {index}"}


def synthesize_value(schema: dict[str, Any], index: int) -> Any:
    """根据单个字段 schema 合成 Mock 值。"""
    enum_values = schema.get("enum")
    if enum_values:
        return enum_values[(index - 1) % len(enum_values)]

    schema_type = schema.get("type")
    if schema_type == "string":
        return f"value_{index}"
    if schema_type == "integer":
        return index
    if schema_type == "number":
        return float(index)
    if schema_type == "boolean":
        return index % 2 == 0
    if schema_type == "array":
        return [synthesize_value(schema.get("items") or {"type": "string"}, index)]
    if schema_type == "object":
        return {
            field_name: synthesize_value(field_schema, index)
            for field_name, field_schema in (schema.get("properties") or {}).items()
        }
    return f"value_{index}"


def build_generation_metadata(
    *,
    command: str,
    generation_model: str,
    batch_index: int,
    generation_mode: str,
) -> dict[str, Any]:
    """构造统一的 synthetic metadata 结构。"""
    return {
        "source": "synthetic_generated",
        "command": command,
        "generation_model": generation_model,
        "batch_index": batch_index,
        "generation_mode": generation_mode,
    }


def normalize_generated_expected_output(
    output_schema_json: dict[str, Any],
    expected_output: BaseModel,
) -> dict[str, Any]:
    """将结构化生成结果归一为内部 expected_output_json 结构。"""
    payload = expected_output.model_dump(mode="json")
    if output_schema_json.get("type") == "string":
        if "answer" in payload:
            return {"answer": payload["answer"]}
        if len(payload) == 1:
            return {"answer": next(iter(payload.values()))}
    return payload


def _build_few_shot_input_fields(field_names: Sequence[str]) -> dict[str, str]:
    """构造 few-shot 示例中的输入字段占位符。"""
    return {field_name: f"<{field_name}_value>" for field_name in field_names}


def _build_few_shot_output_fields(output_schema_json: dict[str, Any]) -> dict[str, str]:
    """构造 few-shot 示例中的输出字段占位符。"""
    if output_schema_json.get("type") == "string":
        return {"answer": "<answer_value>"}

    field_names = (output_schema_json.get("properties") or {"answer": {}}).keys()
    fields = {field_name: f"<{field_name}_value>" for field_name in field_names}
    return fields or {"answer": "<answer_value>"}
