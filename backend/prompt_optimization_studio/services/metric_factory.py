import json
import re
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field

from prompt_optimization_studio.core.exceptions import bad_request
from prompt_optimization_studio.services.openai_client import openai_client_service


class JudgeMetricResult(BaseModel):
    correct: bool
    score: float = Field(ge=0.0, le=1.0)
    rationale: str
    error_type: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


def score_metric(
    metric_name: str,
    prediction: dict[str, Any],
    expected_output_json: dict[str, Any],
    field_name: str | None = None,
    metric_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metric_config = metric_config or {}
    prediction_value = _sanitize_prediction(prediction)
    parse_error = _prediction_meta(prediction).get("error_type")

    if parse_error in {"parse_error", "schema_error"}:
        return _build_result(
            score=0.0,
            correct=False,
            error_type=parse_error,
            actual=prediction_value,
            expected=expected_output_json,
        )

    if metric_name == "exact_match":
        correct = prediction_value == expected_output_json
        return _build_result(
            score=1.0 if correct else 0.0,
            correct=correct,
            error_type=None if correct else "semantic_mismatch",
            actual=prediction_value,
            expected=expected_output_json,
        )

    if metric_name == "normalized_exact_match":
        correct = _normalize_for_match(prediction_value) == _normalize_for_match(expected_output_json)
        return _build_result(
            score=1.0 if correct else 0.0,
            correct=correct,
            error_type=None if correct else "semantic_mismatch",
            actual=prediction_value,
            expected=expected_output_json,
        )

    if metric_name == "contains":
        expected_text = _extract_text(expected_output_json, field_name)
        actual_text = _extract_text(prediction_value, field_name)
        correct = _normalize_whitespace(expected_text) in _normalize_whitespace(actual_text)
        return _build_result(
            score=1.0 if correct else 0.0,
            correct=correct,
            error_type=None if correct else "semantic_mismatch",
            actual=prediction_value,
            expected=expected_output_json,
        )

    if metric_name == "f1_token":
        expected_text = _extract_text(expected_output_json, field_name)
        actual_text = _extract_text(prediction_value, field_name)
        score = _token_f1(expected_text, actual_text)
        return _build_result(
            score=score,
            correct=score >= metric_config.get("correct_threshold", 0.999),
            error_type=None if score > 0 else "semantic_mismatch",
            actual=prediction_value,
            expected=expected_output_json,
        )

    if metric_name == "json_field_accuracy":
        field_name = _ensure_target_field(field_name, expected_output_json)
        expected = expected_output_json.get(field_name)
        actual = prediction_value.get(field_name)
        if field_name not in prediction_value:
            return _build_result(
                score=0.0,
                correct=False,
                error_type="missing_field",
                actual=prediction_value,
                expected=expected_output_json,
            )
        correct = actual == expected
        return _build_result(
            score=1.0 if correct else 0.0,
            correct=correct,
            error_type=None if correct else _classify_field_error(field_name, expected, actual),
            actual=prediction_value,
            expected=expected_output_json,
        )

    if metric_name == "json_all_fields_accuracy":
        strict = bool(metric_config.get("strict", False))
        return _score_json_all_fields(prediction_value, expected_output_json, strict=strict)

    if metric_name == "llm_judge":
        return _score_llm_judge(
            prediction=prediction_value,
            expected_output_json=expected_output_json,
            field_name=field_name,
            metric_config=metric_config,
        )

    if metric_name == "gepa_feedback_metric":
        base_metric = metric_config.get("base_metric", "json_field_accuracy")
        base_result = score_metric(
            metric_name=base_metric,
            prediction=prediction,
            expected_output_json=expected_output_json,
            field_name=field_name,
            metric_config={k: v for k, v in metric_config.items() if k != "base_metric"},
        )
        feedback = _build_gepa_feedback(
            prediction=prediction_value,
            expected_output_json=expected_output_json,
            field_name=field_name,
            base_result=base_result,
        )
        return {
            **base_result,
            "feedback": feedback,
        }

    raise bad_request(f"unsupported metric: {metric_name}")


def _score_json_all_fields(
    prediction: dict[str, Any],
    expected_output_json: dict[str, Any],
    *,
    strict: bool,
) -> dict[str, Any]:
    expected_keys = set(expected_output_json.keys())
    prediction_keys = set(prediction.keys())
    extra_keys = sorted(prediction_keys - expected_keys)
    missing_keys = sorted(expected_keys - prediction_keys)
    if missing_keys:
        return _build_result(
            score=0.0,
            correct=False,
            error_type="missing_field",
            actual=prediction,
            expected=expected_output_json,
        )
    matches = sum(1 for key in expected_keys if prediction.get(key) == expected_output_json.get(key))
    total = max(len(expected_keys), 1)
    score = matches / total
    if strict and extra_keys:
        score = 0.0
        return _build_result(
            score=score,
            correct=False,
            error_type="extra_field",
            actual=prediction,
            expected=expected_output_json,
        )
    correct = score == 1.0 and (not strict or not extra_keys)
    error_type = None if correct else ("extra_field" if extra_keys and strict else "semantic_mismatch")
    return _build_result(
        score=score,
        correct=correct,
        error_type=error_type,
        actual=prediction,
        expected=expected_output_json,
    )


def _score_llm_judge(
    prediction: dict[str, Any],
    expected_output_json: dict[str, Any],
    field_name: str | None,
    metric_config: dict[str, Any],
) -> dict[str, Any]:
    if not openai_client_service.configured:
        # Keep local development usable without an API key.
        expected_text = _extract_text(expected_output_json, field_name)
        actual_text = _extract_text(prediction, field_name)
        score = _token_f1(expected_text, actual_text)
        rationale = "Heuristic fallback judge used because OPENAI_API_KEY is not configured."
        return _build_result(
            score=score,
            correct=score >= metric_config.get("correct_threshold", 0.8),
            error_type=None if score > 0 else "judge_error",
            actual=prediction,
            expected=expected_output_json,
            rationale=rationale,
        )

    judge_model = metric_config.get("judge_model")
    if not judge_model:
        raise bad_request("llm_judge requires metric_config.judge_model")

    instructions = (
        "You are evaluating whether a model prediction satisfies the gold answer. "
        "Return a structured judgment with correct, score, rationale, error_type, and confidence."
    )
    input_text = (
        f"Metric field: {field_name or '<auto>'}\n"
        f"Expected output:\n{json.dumps(expected_output_json, ensure_ascii=False, indent=2)}\n\n"
        f"Model prediction:\n{json.dumps(prediction, ensure_ascii=False, indent=2)}\n\n"
        "Judge semantic correctness, style adherence, and schema alignment."
    )
    try:
        parsed = openai_client_service.generate_structured(
            model=judge_model,
            instructions=instructions,
            input_text=input_text,
            text_format=JudgeMetricResult,
        )
    except Exception as exc:
        return _build_result(
            score=0.0,
            correct=False,
            error_type="judge_error",
            actual=prediction,
            expected=expected_output_json,
            rationale=str(exc),
        )

    return _build_result(
        score=float(parsed.score),
        correct=bool(parsed.correct),
        error_type=parsed.error_type or (None if parsed.correct else "semantic_mismatch"),
        actual=prediction,
        expected=expected_output_json,
        rationale=parsed.rationale,
        confidence=parsed.confidence,
    )


def _build_gepa_feedback(
    prediction: dict[str, Any],
    expected_output_json: dict[str, Any],
    field_name: str | None,
    base_result: dict[str, Any],
) -> str:
    return (
        f"Input focus field: {field_name or 'all fields'}\n"
        f"Expected output: {json.dumps(expected_output_json, ensure_ascii=False)}\n"
        f"Actual output: {json.dumps(prediction, ensure_ascii=False)}\n"
        f"Observed error type: {base_result.get('error_type') or 'none'}\n"
        f"Why it is wrong: {base_result.get('rationale') or 'Prediction does not match the gold answer closely enough.'}\n"
        "Suggested prompt improvement: make the output format stricter, reinforce the target field semantics, "
        "and add a few-shot example for this failure mode."
    )


def _build_result(
    *,
    score: float,
    correct: bool,
    error_type: str | None,
    actual: Any,
    expected: Any,
    rationale: str | None = None,
    confidence: float | None = None,
) -> dict[str, Any]:
    return {
        "score": max(0.0, min(1.0, float(score))),
        "correct": bool(correct),
        "error_type": error_type,
        "actual": actual,
        "expected": expected,
        "rationale": rationale,
        "confidence": confidence,
    }


def _prediction_meta(prediction: Mapping[str, Any]) -> Mapping[str, Any]:
    meta = prediction.get("__meta__")
    return meta if isinstance(meta, Mapping) else {}


def _sanitize_prediction(prediction: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in prediction.items() if not key.startswith("__")}


def _ensure_target_field(field_name: str | None, expected_output_json: dict[str, Any]) -> str:
    if field_name is None:
        field_name = next(iter(expected_output_json.keys()), None)
    if field_name is None:
        raise bad_request("metric requires a target field")
    return field_name


def _extract_text(payload: Any, field_name: str | None = None) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, Mapping):
        if field_name and field_name in payload:
            return _extract_text(payload[field_name])
        if "answer" in payload:
            return _extract_text(payload["answer"])
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if isinstance(payload, list):
        return " ".join(_extract_text(item) for item in payload)
    return str(payload)


def _normalize_for_match(payload: Any) -> str:
    return _normalize_whitespace(_extract_text(payload)).lower()


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _token_f1(expected_text: str, actual_text: str) -> float:
    expected_tokens = _normalize_whitespace(expected_text).lower().split()
    actual_tokens = _normalize_whitespace(actual_text).lower().split()
    if not expected_tokens and not actual_tokens:
        return 1.0
    if not expected_tokens or not actual_tokens:
        return 0.0

    overlap = 0
    remaining = list(actual_tokens)
    for token in expected_tokens:
        if token in remaining:
            overlap += 1
            remaining.remove(token)
    if overlap == 0:
        return 0.0
    precision = overlap / len(actual_tokens)
    recall = overlap / len(expected_tokens)
    return 2 * precision * recall / (precision + recall)


def _classify_field_error(field_name: str, expected: Any, actual: Any) -> str:
    if actual is None:
        return "missing_field"
    if field_name in {"label", "category"}:
        return "wrong_label"
    if type(actual) is not type(expected):
        return "schema_error"
    return "semantic_mismatch"
