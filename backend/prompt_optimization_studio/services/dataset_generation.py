from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, create_model
from sqlalchemy.orm import Session

from prompt_optimization_studio.models.dataset import Dataset
from prompt_optimization_studio.models.project import Project
from prompt_optimization_studio.services.dataset_service import import_dataset_examples
from prompt_optimization_studio.services.openai_client import openai_client_service

StructuredT = TypeVar("StructuredT", bound=BaseModel)


def generate_mock_examples(project: Project, command: str, count: int) -> list[dict[str, Any]]:
    task_key = project.task_key
    output_schema_json = project.output_schema_json or {}
    examples: list[dict[str, Any]] = []
    for index in range(1, count + 1):
        text = f"{command} 示例 {index}"
        if task_key == "classification":
            expected_output = {"label": ["refund", "logistics", "account", "complaint", "other"][(index - 1) % 5]}
        elif task_key == "rewriting":
            expected_output = {"answer": f"改写结果 {index}"}
        elif task_key == "qa":
            expected_output = {"answer": f"问题 {index} 的回答"}
        else:
            expected_output = synthesize_output_from_schema(output_schema_json, index)

        examples.append(
            {
                "input_json": {"text": text},
                "expected_output_json": expected_output,
                "metadata_json": {"source": "synthetic_generated", "command": command},
            }
        )
    return examples


class SyntheticInputModel(BaseModel):
    text: str


def generate_openai_examples(project: Project, command: str, count: int, generation_model: str) -> list[dict[str, Any]]:
    output_model = build_output_model(project.output_schema_json or {})
    example_model = create_model(
        "SyntheticExampleModel",
        __config__=ConfigDict(extra="forbid"),
        text=(str, ...),
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
        "The expected_output field must satisfy the declared schema exactly."
    )
    input_text = (
        f"Task key: {project.task_key}\n"
        f"Task description: {project.task_description or project.description or ''}\n"
        f"Command: {command}\n"
        f"Count: {count}\n"
        f"Input schema: {project.input_schema_json}\n"
        f"Output schema: {project.output_schema_json}\n"
        "Produce varied examples, including short and long phrasing, edge cases, and realistic wording."
    )
    parsed = openai_client_service.generate_structured(
        model=generation_model,
        instructions=instructions,
        input_text=input_text,
        text_format=batch_model,
    )
    return [
        {
            "input_json": {"text": item.text},
            "expected_output_json": item.expected_output.model_dump(mode="json"),
            "metadata_json": {"source": "synthetic_generated", "command": command},
        }
        for item in parsed.items
    ]


def create_generated_dataset(
    db: Session,
    project: Project,
    name: str,
    command: str,
    count: int,
    generation_model: str,
    quality_status: str,
) -> tuple[Dataset, int]:
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
        quality_status=quality_status,
    )
    return dataset, len(created)


def build_output_model(output_schema_json: dict[str, Any]) -> type[BaseModel]:
    schema_type = output_schema_json.get("type")
    if schema_type != "object":
        return create_model(
            "GeneratedOutputModel",
            __config__=ConfigDict(extra="forbid"),
            answer=(str, ...),
        )

    fields: dict[str, tuple[Any, Any]] = {}
    required = set(output_schema_json.get("required", []))
    for field_name, field_schema in (output_schema_json.get("properties") or {}).items():
        annotation = schema_to_annotation(field_schema, suffix=field_name.title())
        default = ... if field_name in required else None
        fields[field_name] = (annotation, default)

    if not fields:
        fields["answer"] = (str, ...)

    return create_model("GeneratedOutputModel", __config__=ConfigDict(extra="forbid"), **fields)


def schema_to_annotation(schema: dict[str, Any], *, suffix: str) -> Any:
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
        nested_model.__name__ = f"{suffix}OutputModel"
        return nested_model
    return str


def synthesize_output_from_schema(output_schema_json: dict[str, Any], index: int) -> dict[str, Any]:
    schema_type = output_schema_json.get("type")
    if schema_type != "object":
        return {"answer": f"synthetic answer {index}"}

    payload: dict[str, Any] = {}
    for field_name, field_schema in (output_schema_json.get("properties") or {}).items():
        payload[field_name] = synthesize_value(field_schema, index)
    return payload or {"answer": f"synthetic answer {index}"}


def synthesize_value(schema: dict[str, Any], index: int) -> Any:
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
