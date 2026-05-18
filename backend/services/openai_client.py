"""OpenAI 客户端服务封装。

提供统一的文本生成和结构化输出接口, 兼容 OpenAI 和第三方兼容 API。
"""

import json
from typing import Any, NoReturn, TypeVar

from openai import APIConnectionError, OpenAI

from backend.core.config import get_settings
from backend.core.exceptions import bad_request

StructuredT = TypeVar("StructuredT")


class OpenAIClientService:
    """OpenAI API 客户端服务, 封装文本生成与结构化输出。"""

    @property
    def configured(self) -> bool:
        """检查 API Key 是否已配置。"""
        return bool(get_settings().openai_api_key)

    def _build_client(self) -> OpenAI:
        settings = get_settings()
        if not settings.openai_api_key:
            raise bad_request("OPENAI_API_KEY is not configured")
        client_kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
        return OpenAI(**client_kwargs)

    def generate_text(self, model: str, prompt: str, **kwargs: Any) -> str:
        """使用指定模型生成文本响应。

        Args:
            model: 模型名称。
            prompt: 输入提示文本。
            **kwargs: 额外参数, 如 temperature、max_tokens。

        Returns:
            生成的文本内容。
        """
        client = self._build_client()
        resolved_model = self._resolve_model_name(model)
        try:
            if self._use_responses_api():
                response = client.responses.create(
                    model=resolved_model,
                    input=prompt,
                    **kwargs,
                )
                return response.output_text

            response = client.chat.completions.create(
                model=resolved_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get("temperature"),
                max_tokens=kwargs.get("max_tokens"),
                extra_body=self._compatible_extra_body(kwargs.get("extra_body")),
            )
        except APIConnectionError as exc:
            self._raise_provider_unavailable(exc)

        content = response.choices[0].message.content
        if isinstance(content, list):
            return "".join(
                block.text for block in content if hasattr(block, "text") and block.text is not None
            ).strip()
        return (content or "").strip()

    def generate_structured(
        self,
        model: str,
        instructions: str,
        input_text: str,
        text_format: type[StructuredT],
        **kwargs: Any,
    ) -> StructuredT:
        """使用指定模型生成结构化输出。

        Args:
            model: 模型名称。
            instructions: 系统指令文本。
            input_text: 用户输入文本。
            text_format: 期望输出的 Pydantic 模型类型。
            **kwargs: 额外参数。

        Returns:
            解析后的结构化输出实例。
        """
        client = self._build_client()
        resolved_model = self._resolve_model_name(model)
        try:
            if self._use_responses_api():
                response = client.responses.parse(
                    model=resolved_model,
                    instructions=instructions,
                    input=input_text,
                    text_format=text_format,
                    **kwargs,
                )
                parsed = response.output_parsed
                if parsed is None:
                    raise bad_request("OpenAI structured response did not return parsed content")
                return parsed

            # OpenAI-compatible providers such as DeepSeek commonly expose chat completions
            # but not the responses API. We request JSON and validate it locally.
            schema_json = text_format.model_json_schema()
            schema_instruction = (
                "Return JSON only. Do not include markdown fences or explanatory text.\n"
                f"The response MUST be a JSON object that exactly matches this schema:\n"
                f"{json.dumps(schema_json, ensure_ascii=False)}\n"
                "Use the exact field names shown in the schema. Do not rename any fields."
            )
            response = client.chat.completions.create(
                model=resolved_model,
                messages=[
                    {"role": "system", "content": f"{instructions}\n\n{schema_instruction}"},
                    {"role": "user", "content": input_text},
                ],
                response_format={"type": "json_object"},
                temperature=kwargs.get("temperature", 0),
                max_tokens=kwargs.get("max_tokens"),
                extra_body=self._compatible_extra_body(kwargs.get("extra_body")),
            )
        except APIConnectionError as exc:
            self._raise_provider_unavailable(exc)

        content = response.choices[0].message.content
        if isinstance(content, list):
            raw_text = "".join(
                block.text for block in content if hasattr(block, "text") and block.text is not None
            )
        else:
            raw_text = content or ""
        try:
            raw_payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise bad_request("OpenAI-compatible provider returned invalid JSON content") from exc

        if not hasattr(text_format, "model_validate"):
            raise bad_request("text_format must be a Pydantic model type")
        return text_format.model_validate(raw_payload)

    def _use_responses_api(self) -> bool:
        settings = get_settings()
        base_url = (settings.openai_base_url or "").strip().lower()
        return not base_url or "api.openai.com" in base_url

    def _resolve_model_name(self, model: str) -> str:
        if model.startswith("openai/"):
            return model.split("/", 1)[1]
        return model

    def _compatible_extra_body(self, existing: dict[str, Any] | None) -> dict[str, Any]:
        payload = dict(existing or {})
        payload.setdefault("thinking", {"type": "disabled"})
        return payload

    def _raise_provider_unavailable(self, exc: APIConnectionError) -> NoReturn:
        """将底层连接错误转换为明确的业务错误。"""
        settings = get_settings()
        if settings.openai_base_url:
            raise bad_request(
                f"当前 LLM 服务不可用，请检查 OPENAI_BASE_URL={settings.openai_base_url} 对应服务是否启动。"
            ) from exc
        raise bad_request("当前 LLM 服务不可用，请检查 OpenAI 网络连接和模型服务状态。") from exc


openai_client_service = OpenAIClientService()
