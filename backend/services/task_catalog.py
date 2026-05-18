"""内置任务模板目录。

定义问答、JSON 生成、评分等预置任务模板及其配置。
"""

import copy
from dataclasses import dataclass
from typing import Any

from backend.core.constants import BUILTIN_TASK_KEYS

TemplateLocale = str
DEFAULT_TEMPLATE_LOCALE = "en"
SUPPORTED_TEMPLATE_LOCALES = {"en", "zh"}

TEXT_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
    },
    "required": ["text"],
}


@dataclass(frozen=True)
class BuiltinTaskTemplate:
    """内置任务模板定义, 包含多语言显示名称、输入输出 schema 和默认指标配置。"""

    task_display_name: dict[TemplateLocale, str]
    task_description: dict[TemplateLocale, str]
    input_schema_json: dict[str, Any]
    output_schema_json: dict[str, Any]
    default_metric_config_json: dict[str, Any]
    task_definition_json: dict[str, Any]
    report_profile_json: dict[str, Any]


BUILTIN_TASK_ORDER = (
    "qa",
    "json_generation",
    "rate",
)

BUILTIN_TASK_TEMPLATES: dict[str, BuiltinTaskTemplate] = {
    "qa": BuiltinTaskTemplate(
        task_display_name={"en": "Question Answering", "zh": "问答任务"},
        task_description={
            "en": "Answer the question grounded in the provided text and return a concise answer.",
            "zh": "基于给定文本回答问题, 返回简洁答案, 适合 FAQ、知识问答和检索后回答场景。",
        },
        input_schema_json=TEXT_INPUT_SCHEMA,
        output_schema_json={
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
            },
            "required": ["answer"],
        },
        default_metric_config_json={
            "metric": "f1_token",
            "field": "answer",
            "correct_threshold": 0.8,
        },
        task_definition_json={
            "task_family": "qa",
            "target_field": "answer",
            "grounded": True,
            "answer_style": "concise",
        },
        report_profile_json={
            "task_family": "qa",
            "primary_output_field": "answer",
            "focus_areas": [
                "answer_overlap",
                "hallucination_risk",
                "coverage",
            ],
        },
    ),
    "json_generation": BuiltinTaskTemplate(
        task_display_name={"en": "JSON Generation", "zh": "JSON 生成"},
        task_description={
            "en": "Generate a JSON object that follows the requested structure and stays machine-parseable.",
            "zh": "生成符合指定结构的 JSON 对象, 重点关注可解析性、字段完整性和 schema 一致性。",
        },
        input_schema_json=TEXT_INPUT_SCHEMA,
        output_schema_json={
            "type": "object",
            "properties": {
                "result": {"type": "object"},
                "notes": {"type": "string"},
            },
            "required": ["result"],
        },
        default_metric_config_json={
            "metric": "json_field_accuracy",
            "field": "result",
        },
        task_definition_json={
            "task_family": "json_generation",
            "target_field": "result",
            "must_parse_as_json": True,
            "strict_schema_adherence": True,
        },
        report_profile_json={
            "task_family": "json_generation",
            "primary_output_field": "result",
            "focus_areas": [
                "json_parseability",
                "schema_adherence",
                "extra_fields",
            ],
        },
    ),
    "rate": BuiltinTaskTemplate(
        task_display_name={"en": "Rating", "zh": "评分任务"},
        task_description={
            "en": "Score the input against the rubric and return a numeric score plus concise reasoning.",
            "zh": "根据评分标准为输入打分, 返回数值分数和简要理由, 适合质检、审核和偏好评估场景。",
        },
        input_schema_json=TEXT_INPUT_SCHEMA,
        output_schema_json={
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "reasoning": {"type": "string"},
            },
            "required": ["score"],
        },
        default_metric_config_json={
            "metric": "weighted_numeric_fields_accuracy",
            "scoring_mode": "linear_decay",
            "fields": [
                {"name": "score", "weight": 1.0, "scale": 5.0},
            ],
            "pass_threshold": 0.8,
            "strict_missing": True,
        },
        task_definition_json={
            "task_family": "rating",
            "target_field": "score",
            "score_range": {"min": 0, "max": 5},
            "include_reasoning": True,
        },
        report_profile_json={
            "task_family": "rating",
            "primary_output_field": "score",
            "focus_areas": [
                "score_accuracy",
                "reasoning_consistency",
                "rubric_alignment",
            ],
        },
    ),
}


def _clone(value: Any) -> Any:
    return copy.deepcopy(value)


def normalize_template_locale(locale: str | None) -> str:
    """规范化模板语言代码, 无效值回退为默认语言。"""
    if locale in SUPPORTED_TEMPLATE_LOCALES:
        return locale
    return DEFAULT_TEMPLATE_LOCALE


def get_builtin_task_template(task_key: str) -> BuiltinTaskTemplate:
    """根据任务键获取内置任务模板。"""
    return BUILTIN_TASK_TEMPLATES[task_key]


def list_builtin_task_templates(locale: str | None = None) -> list[dict[str, Any]]:
    """列出所有内置任务模板的序列化表示。"""
    resolved_locale = normalize_template_locale(locale)
    return [
        serialize_builtin_task_template(task_key, locale=resolved_locale)
        for task_key in BUILTIN_TASK_ORDER
    ]


def serialize_builtin_task_template(task_key: str, *, locale: str | None = None) -> dict[str, Any]:
    """将内置任务模板序列化为字典, 使用指定语言。"""
    template = get_builtin_task_template(task_key)
    resolved_locale = normalize_template_locale(locale)
    return {
        "task_key": task_key,
        "task_display_name": template.task_display_name[resolved_locale],
        "task_description": template.task_description[resolved_locale],
        "input_schema_json": _clone(template.input_schema_json),
        "output_schema_json": _clone(template.output_schema_json),
        "default_metric_config_json": _clone(template.default_metric_config_json),
        "task_definition_json": _clone(template.task_definition_json),
        "report_profile_json": _clone(template.report_profile_json),
    }


def resolve_project_create_payload(payload) -> dict[str, Any]:
    """解析项目创建请求, 对内置任务自动填充模板默认值。"""
    data = payload.model_dump(exclude={"template_locale"})
    if payload.task_kind != "builtin":
        return data

    template_payload = serialize_builtin_task_template(
        payload.task_key,
        locale=getattr(payload, "template_locale", None),
    )
    fields_set = set(payload.model_fields_set)
    for field_name, template_value in template_payload.items():
        if field_name == "task_key":
            continue
        current_value = data.get(field_name)
        if field_name not in fields_set or current_value is None:
            data[field_name] = template_value
    return data


if set(BUILTIN_TASK_TEMPLATES) != BUILTIN_TASK_KEYS:
    raise RuntimeError("BUILTIN_TASK_TEMPLATES must stay in sync with BUILTIN_TASK_KEYS")
