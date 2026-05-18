"""运行默认配置解析工具。

负责在创建评测或优化任务时，根据项目默认指标配置和后端环境变量
推导运行所需的 metric 与模型配置。
"""

from typing import Any

from backend.core.config import get_settings
from backend.core.exceptions import bad_request


def resolve_project_metric_config(default_metric_config_json: dict[str, Any]) -> dict[str, Any]:
    """解析项目默认指标配置，作为运行期指标快照。

    Args:
        default_metric_config_json: 项目上的默认指标配置。

    Returns:
        可直接用于评测或优化运行的指标配置副本。
    """
    if not default_metric_config_json:
        raise bad_request("project default metric configuration is required")
    return dict(default_metric_config_json)


def build_default_model_config() -> dict[str, Any]:
    """根据后端环境变量构造默认模型配置。

    Returns:
        运行期模型配置。若未配置真实模型，则回退到 mock。
    """
    settings = get_settings()
    if not settings.openai_api_key:
        return {
            "provider": "mock",
            "model": "mock",
        }
    return {
        "provider": "openai",
        "model": settings.openai_default_model,
    }
