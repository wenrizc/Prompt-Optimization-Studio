import hashlib
import json
import re
from typing import Any

from prompt_optimization_studio.core.constants import BUILTIN_TASK_KEYS
from prompt_optimization_studio.core.exceptions import bad_request
from prompt_optimization_studio.schemas.prompt import TEMPLATE_VAR_PATTERN

RESERVED_TASK_KEYS = BUILTIN_TASK_KEYS | {"builtin", "custom", "all"}


def ensure_task_key_allowed(task_kind: str, task_key: str) -> None:
    if task_kind == "custom" and task_key in RESERVED_TASK_KEYS:
        raise bad_request("custom task_key cannot use a reserved system keyword")


def ensure_json_schema_object(schema_value: dict[str, Any], field_name: str) -> None:
    if not isinstance(schema_value, dict):
        raise bad_request(f"{field_name} must be a JSON object")


def validate_prompt_template(user_template: str) -> tuple[list[str], list[str]]:
    variables = sorted(set(TEMPLATE_VAR_PATTERN.findall(user_template)))
    if "text" not in variables:
        raise bad_request("user_template must reference {text}")

    unknown_variables = sorted(set(variables) - {"text"})
    if unknown_variables:
        joined = ", ".join(unknown_variables)
        raise bad_request(f"user_template contains unknown variables: {joined}")

    warnings: list[str] = []
    if len(user_template) > 6000:
        warnings.append("Prompt template is long and may increase runtime cost")
    return variables, warnings


def ensure_prompt_schema_compatible(output_schema_json: dict[str, Any]) -> list[str]:
    ensure_json_schema_object(output_schema_json, "output_schema_json")
    warnings: list[str] = []
    schema_type = output_schema_json.get("type")
    if schema_type not in (None, "object"):
        warnings.append("Current MVP is optimized for object-shaped output schemas")
    return warnings


def compute_example_content_hash(input_json: dict[str, Any], expected_output_json: dict[str, Any]) -> str:
    payload = {
        "input_json": input_json,
        "expected_output_json": expected_output_json,
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
