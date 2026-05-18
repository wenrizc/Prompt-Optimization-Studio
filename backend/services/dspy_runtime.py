"""DSPy 运行时配置服务。

负责初始化 DSPy 语言模型运行时, 包括 Mock 模式和 OpenAI 兼容模式。
"""

from dataclasses import dataclass
from typing import Any

from backend.core.config import get_settings
from backend.core.exceptions import bad_request


@dataclass
class RuntimeHandle:
    """DSPy 运行时句柄, 封装模型提供者和语言模型实例。"""

    provider: str
    configured: bool
    model: str | None = None
    lm: Any | None = None


def configure_runtime(model_config_json: dict[str, Any]) -> RuntimeHandle:
    """根据模型配置初始化并配置 DSPy 运行时。

    Args:
        model_config_json: 模型配置字典, 包含 provider、model 等字段。

    Returns:
        初始化完成的 RuntimeHandle 实例。
    """
    provider = model_config_json.get("provider", "mock")
    if provider == "mock":
        return RuntimeHandle(provider="mock", configured=True, model="mock", lm=None)

    try:
        import dspy  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on optional dependency
        raise bad_request("DSPy is not installed; use provider=mock or install dspy") from exc

    lm_name = model_config_json.get("model")
    if not lm_name:
        raise bad_request("model_config_json.model is required for DSPy runtime")

    settings = get_settings()
    lm_kwargs: dict[str, Any] = {}
    if settings.openai_api_key:
        lm_kwargs["api_key"] = settings.openai_api_key
    if "temperature" in model_config_json:
        lm_kwargs["temperature"] = model_config_json["temperature"]
    if "max_tokens" in model_config_json:
        lm_kwargs["max_tokens"] = model_config_json["max_tokens"]
    if "cache" in model_config_json:
        lm_kwargs["cache"] = model_config_json["cache"]
    if provider == "openai" and "/" not in lm_name:
        lm_name = f"openai/{lm_name}"

    if "model_type" in model_config_json:
        lm_kwargs["model_type"] = model_config_json["model_type"]
    elif lm_name.startswith("openai/"):
        if settings.openai_base_url and "api.openai.com" not in settings.openai_base_url.lower():
            lm_kwargs["model_type"] = "chat"
        else:
            lm_kwargs["model_type"] = "responses"
    if settings.openai_base_url:
        lm_kwargs["api_base"] = settings.openai_base_url
        if "deepseek.com" in settings.openai_base_url.lower():
            lm_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

    lm = dspy.LM(lm_name, **lm_kwargs)
    # 重置线程所有权，允许当前线程调用 dspy.configure。
    # Worker 是单线程串行执行，不存在并发竞争。
    import dspy.dsp.utils.settings as _dspy_settings_mod
    _dspy_settings_mod.config_owner_thread_id = None
    dspy.configure(lm=lm)
    return RuntimeHandle(provider=provider, configured=True, model=lm_name, lm=lm)
