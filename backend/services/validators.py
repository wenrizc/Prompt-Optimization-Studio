"""输入校验工具集。

提供任务键、JSON Schema、提示词模板与跨字段任务契约的统一校验能力。
"""

import hashlib
import json
from typing import Any

from backend.core.constants import BUILTIN_TASK_KEYS
from backend.core.exceptions import bad_request
from backend.schemas.prompt import TEMPLATE_VAR_PATTERN

RESERVED_TASK_KEYS = BUILTIN_TASK_KEYS | {"builtin", "custom", "all"}
SUPPORTED_SIGNATURE_FIELD_TYPES = {"string", "number", "integer", "boolean"}
SUPPORTED_OUTPUT_SCHEMA_TYPES = {"object", "string"}


def ensure_task_key_allowed(task_kind: str, task_key: str) -> None:
    """校验自定义任务键是否使用了系统保留关键字。"""
    if task_kind == "custom" and task_key in RESERVED_TASK_KEYS:
        raise bad_request("custom task_key cannot use a reserved system keyword")


def ensure_json_schema_object(schema_value: dict[str, Any], field_name: str) -> None:
    """校验指定字段是否为有效的 JSON 对象。"""
    if not isinstance(schema_value, dict):
        raise bad_request(f"{field_name} must be a JSON object")


def validate_generated_template_alignment(template: dict[str, Any]) -> None:
    """校验生成的自定义任务模板配置是否彼此一致。"""
    try:
        validate_task_contract_alignment(template, task_kind="custom")
    except Exception as exc:  # pragma: no cover - pydantic 需要 ValueError 语义
        raise ValueError(str(exc)) from exc


def validate_prompt_template(
    user_template: str,
    input_schema_json: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """校验提示词模板的合法性。

    Args:
        user_template: 用户模板文本。
        input_schema_json: 项目输入 schema。

    Returns:
        包含变量列表和警告列表的元组。
    """
    allowed_variables = set(get_signature_input_fields(input_schema_json))
    variables = sorted(set(TEMPLATE_VAR_PATTERN.findall(user_template)))
    if not variables:
        raise bad_request("user_template must reference at least one input variable")

    unknown_variables = sorted(set(variables) - allowed_variables)
    if unknown_variables:
        joined = ", ".join(unknown_variables)
        raise bad_request(f"user_template contains unknown variables: {joined}")

    warnings: list[str] = []
    if len(user_template) > 6000:
        warnings.append("Prompt template is long and may increase runtime cost")
    return variables, warnings


def ensure_prompt_schema_compatible(output_schema_json: dict[str, Any]) -> list[str]:
    """校验输出 schema 是否在当前平台支持范围内。"""
    validate_supported_output_schema(output_schema_json)
    return []


def validate_task_contract_alignment(
    payload: dict[str, Any],
    *,
    task_kind: str,
) -> None:
    """校验任务契约的跨字段一致性。"""
    task_key = payload.get("task_key")
    if not isinstance(task_key, str) or not task_key.strip():
        raise bad_request("task_key is required")
    ensure_task_key_allowed(task_kind, task_key)

    input_schema_json = payload.get("input_schema_json") or {}
    output_schema_json = payload.get("output_schema_json") or {}
    get_signature_input_fields(input_schema_json)
    validate_supported_output_schema(output_schema_json)

    schema_type = output_schema_json.get("type")
    properties = output_schema_json.get("properties") or {}
    output_fields = set(properties)

    default_metric_config_json = payload.get("default_metric_config_json") or {}
    task_definition_json = payload.get("task_definition_json") or {}
    report_profile_json = payload.get("report_profile_json") or {}

    if schema_type == "object":
        if not output_fields:
            raise bad_request("output_schema_json.properties must define at least one field")
        _validate_field_reference(
            default_metric_config_json.get("field"),
            output_fields,
            "default_metric_config_json.field",
            required=False,
        )
        _validate_field_reference(
            task_definition_json.get("target_field"),
            output_fields,
            "task_definition_json.target_field",
            required=True,
        )
        _validate_field_reference(
            report_profile_json.get("primary_output_field"),
            output_fields,
            "report_profile_json.primary_output_field",
            required=True,
        )
    else:
        _validate_string_output_field_alias(
            default_metric_config_json.get("field"),
            "default_metric_config_json.field",
        )
        _validate_string_output_field_alias(
            task_definition_json.get("target_field"),
            "task_definition_json.target_field",
        )
        _validate_string_output_field_alias(
            report_profile_json.get("primary_output_field"),
            "report_profile_json.primary_output_field",
        )

    focus_areas = report_profile_json.get("focus_areas")
    if not isinstance(focus_areas, list) or not focus_areas:
        raise bad_request("report_profile_json.focus_areas must be a non-empty string list")
    if not all(isinstance(item, str) and item.strip() for item in focus_areas):
        raise bad_request("report_profile_json.focus_areas must be a non-empty string list")


def get_signature_input_fields(input_schema_json: dict[str, Any]) -> list[str]:
    """解析并校验可映射为 DSPy 输入的字段列表。"""
    ensure_json_schema_object(input_schema_json, "input_schema_json")
    if input_schema_json.get("type") != "object":
        raise bad_request("input_schema_json.type must be 'object'")

    properties = input_schema_json.get("properties")
    if not isinstance(properties, dict) or not properties:
        raise bad_request("input_schema_json.properties must define at least one field")

    field_names = list(properties.keys())
    for field_name, field_schema in properties.items():
        if not isinstance(field_schema, dict):
            raise bad_request(f"input schema for field '{field_name}' must be an object")
        field_type = field_schema.get("type")
        if field_type not in SUPPORTED_SIGNATURE_FIELD_TYPES:
            raise bad_request(
                f"input schema field '{field_name}' must use one of: "
                f"{', '.join(sorted(SUPPORTED_SIGNATURE_FIELD_TYPES))}"
            )
    return field_names


def get_required_input_fields(input_schema_json: dict[str, Any]) -> set[str]:
    """读取输入 schema 中的必填字段集合。"""
    required = input_schema_json.get("required") or []
    if not isinstance(required, list):
        raise bad_request("input_schema_json.required must be a string list")
    return {field for field in required if isinstance(field, str)}


def validate_supported_output_schema(output_schema_json: dict[str, Any]) -> None:
    """校验输出 schema 是否在当前平台正式支持范围内。"""
    ensure_json_schema_object(output_schema_json, "output_schema_json")
    schema_type = output_schema_json.get("type")
    if schema_type not in SUPPORTED_OUTPUT_SCHEMA_TYPES:
        allowed = ", ".join(sorted(SUPPORTED_OUTPUT_SCHEMA_TYPES))
        raise bad_request(f"output_schema_json.type must be one of: {allowed}")

    if schema_type == "object":
        properties = output_schema_json.get("properties")
        if not isinstance(properties, dict) or not properties:
            raise bad_request("output_schema_json.properties must define at least one field")
    if (
        schema_type == "string"
        and "properties" in output_schema_json
        and output_schema_json.get("properties") not in ({}, None)
    ):
        raise bad_request("string output schemas must not declare object properties")


def compute_example_content_hash(
    input_json: dict[str, Any], expected_output_json: dict[str, Any]
) -> str:
    """计算样本内容的 SHA-256 哈希, 用于重复检测。"""
    payload = {
        "input_json": input_json,
        "expected_output_json": expected_output_json,
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _validate_field_reference(
    field_name: Any,
    output_fields: set[str],
    label: str,
    *,
    required: bool,
) -> None:
    if field_name is None:
        if required:
            raise bad_request(f"{label} must exist in output_schema_json.properties")
        return
    if not isinstance(field_name, str) or field_name not in output_fields:
        raise bad_request(f"{label} must exist in output_schema_json.properties")


def _validate_string_output_field_alias(field_name: Any, label: str) -> None:
    if field_name is None:
        return
    if field_name != "answer":
        raise bad_request(f"{label} must be omitted or set to 'answer' for string outputs")
