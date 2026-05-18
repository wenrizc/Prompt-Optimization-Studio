"""自定义任务模板草稿生成服务。"""

from backend.core.config import get_settings
from backend.schemas.custom_task_template_generation import (
    CustomTaskTemplateDraftBundle,
)
from backend.services.openai_client import openai_client_service


def generate_custom_task_template_draft_bundle(prompt: str) -> CustomTaskTemplateDraftBundle:
    """根据自然语言描述生成自定义任务模板草稿。

    Args:
        prompt: 用户输入的自然语言任务描述。

    Returns:
        包含模板草稿与说明的结构化结果。
    """
    instructions = (
        "You generate custom task template drafts for a prompt optimization studio. "
        "Return one minimal but usable template draft plus explanation metadata. "
        "The draft must keep task_key, output field references, metric field, target_field, "
        "and primary_output_field internally aligned. "
        "Prefer top-level object schemas with concise fields. "
        "Do not include markdown. "
        "Guidance must explain each configuration item, what fields can be changed, "
        "how the platform will use it later, and at least one example where appropriate."
    )
    input_text = (
        "Generate a custom task template draft from the following requirement.\n"
        f"Requirement:\n{prompt}\n\n"
        "The response must include:\n"
        "- draft.task_key, draft.task_display_name, draft.task_description\n"
        "- draft.input_schema_json\n"
        "- draft.output_schema_json\n"
        "- draft.default_metric_config_json\n"
        "- draft.task_definition_json\n"
        "- draft.report_profile_json\n"
        "- guidance.overview\n"
        "- guidance.items for task_identity, input_schema_json, output_schema_json, "
        "default_metric_config_json, task_definition_json, report_profile_json\n"
        "Use Chinese for user-facing guidance text.\n\n"
        "The top-level JSON keys MUST be exactly \"draft\" and \"guidance\".\n"
        "Example of the required top-level structure:\n"
        '{"draft": {"task_key": "...", "task_display_name": "...", "task_description": "...", '
        '"input_schema_json": {}, "output_schema_json": {}, "default_metric_config_json": {}, '
        '"task_definition_json": {}, "report_profile_json": {}}, '
        '"guidance": {"overview": "...", "items": {}}}'
    )
    return openai_client_service.generate_structured(
        model=get_settings().openai_default_model,
        instructions=instructions,
        input_text=input_text,
        text_format=CustomTaskTemplateDraftBundle,
    )
