import os
from dataclasses import dataclass
from typing import Any

from prompt_optimization_studio.core.exceptions import bad_request


@dataclass
class RuntimeHandle:
    provider: str
    configured: bool
    model: str | None = None
    lm: Any | None = None


def configure_runtime(model_config_json: dict[str, Any]) -> RuntimeHandle:
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

    from prompt_optimization_studio.core.config import get_settings

    settings = get_settings()
    if settings.openai_api_key and "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.openai_base_url and "OPENAI_BASE_URL" not in os.environ:
        os.environ["OPENAI_BASE_URL"] = settings.openai_base_url

    lm_kwargs: dict[str, Any] = {}
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
    dspy.configure(lm=lm)
    return RuntimeHandle(provider=provider, configured=True, model=lm_name, lm=lm)
