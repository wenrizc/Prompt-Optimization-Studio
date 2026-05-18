import json
from typing import Any, TypeVar

from openai import OpenAI

from prompt_optimization_studio.core.config import get_settings
from prompt_optimization_studio.core.exceptions import bad_request

StructuredT = TypeVar("StructuredT")


class OpenAIClientService:
    @property
    def configured(self) -> bool:
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
        client = self._build_client()
        resolved_model = self._resolve_model_name(model)
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
        client = self._build_client()
        resolved_model = self._resolve_model_name(model)
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
        schema_instruction = (
            "Return JSON only. The JSON must exactly match the requested schema shape. "
            "Do not include markdown fences or explanatory text."
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


openai_client_service = OpenAIClientService()
