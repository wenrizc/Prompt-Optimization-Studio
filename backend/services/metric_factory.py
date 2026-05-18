"""指标计算工厂。

提供多种评估指标实现, 包括精确匹配、F1、字段准确率和 LLM 评判等。
"""

import json
import re
from collections.abc import Mapping
from typing import Any

from openai import APIError
from pydantic import BaseModel, Field

from backend.core.exceptions import bad_request
from backend.services.openai_client import openai_client_service


class JudgeMetricResult(BaseModel):
    """LLM 评判指标的结构化返回模型。"""

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
    """根据指标名称计算预测结果的评分。

    Args:
        metric_name: 指标名称, 如 exact_match、f1_token、llm_judge 等。
        prediction: 模型预测结果。
        expected_output_json: 期望输出。
        field_name: 目标字段名。
        metric_config: 指标配置参数。

    Returns:
        包含 score、correct、error_type 等字段的评分字典。
    """
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
        correct = _normalize_for_match(prediction_value) == _normalize_for_match(
            expected_output_json
        )
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

    if metric_name == "weighted_numeric_fields_accuracy":
        return _score_weighted_numeric_fields(
            prediction=prediction_value,
            expected_output_json=expected_output_json,
            metric_config=metric_config,
        )

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
    matches = sum(
        1 for key in expected_keys if prediction.get(key) == expected_output_json.get(key)
    )
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
    error_type = (
        None if correct else ("extra_field" if extra_keys and strict else "semantic_mismatch")
    )
    return _build_result(
        score=score,
        correct=correct,
        error_type=error_type,
        actual=prediction,
        expected=expected_output_json,
    )


def _score_weighted_numeric_fields(
    prediction: dict[str, Any],
    expected_output_json: dict[str, Any],
    metric_config: dict[str, Any],
) -> dict[str, Any]:
    scoring_mode = _resolve_weighted_numeric_scoring_mode(metric_config)
    field_configs = _parse_weighted_numeric_field_configs(metric_config, scoring_mode)
    pass_threshold = float(metric_config.get("pass_threshold", 1.0))
    strict_missing = bool(metric_config.get("strict_missing", True))

    field_scores: list[dict[str, Any]] = []
    weighted_score = 0.0
    total_weight = sum(config["weight"] for config in field_configs)

    for config in field_configs:
        field_name = config["name"]
        expected_value = expected_output_json.get(field_name)
        actual_value = prediction.get(field_name)

        if field_name not in expected_output_json:
            raise bad_request(f"metric field '{field_name}' is missing from expected output")
        if not _is_numeric_value(expected_value):
            raise bad_request(f"metric field '{field_name}' expected value must be numeric")
        if field_name not in prediction:
            field_scores.append(
                _build_weighted_numeric_field_score(
                    config=config,
                    expected_value=expected_value,
                    actual_value=actual_value,
                    score=0.0,
                    difference=None,
                    field_error_type="missing_field",
                )
            )
            if strict_missing:
                return _build_result(
                    score=0.0,
                    correct=False,
                    error_type="missing_field",
                    actual=prediction,
                    expected=expected_output_json,
                    extra_fields={"field_scores": field_scores},
                )
            field_score = 0.0
        else:
            if not _is_numeric_value(actual_value):
                difference = None
                field_score = 0.0
                field_error_type = "non_numeric_field"
            else:
                difference = abs(float(actual_value) - float(expected_value))
                field_score = _score_weighted_numeric_field_difference(
                    difference=difference,
                    config=config,
                    scoring_mode=scoring_mode,
                )
                field_error_type = None
            field_scores.append(
                _build_weighted_numeric_field_score(
                    config=config,
                    expected_value=expected_value,
                    actual_value=actual_value,
                    score=field_score,
                    difference=difference,
                    field_error_type=field_error_type,
                )
            )

        weighted_score += config["weight"] * field_score

    final_score = weighted_score / total_weight
    correct = final_score >= pass_threshold
    return _build_result(
        score=final_score,
        correct=correct,
        error_type=_resolve_weighted_numeric_error_type(field_scores, correct),
        actual=prediction,
        expected=expected_output_json,
        extra_fields={"field_scores": field_scores},
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
        "Judge semantic correctness, style adherence, and schema alignment.\n\n"
        "Example of the required JSON response format:\n"
        '{"correct": true, "score": 0.95, "rationale": "The prediction matches the expected answer closely.", "error_type": null, "confidence": 0.9}'
    )
    try:
        parsed = openai_client_service.generate_structured(
            model=judge_model,
            instructions=instructions,
            input_text=input_text,
            text_format=JudgeMetricResult,
        )
    except (APIError, ValueError) as exc:
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
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "score": max(0.0, min(1.0, float(score))),
        "correct": bool(correct),
        "error_type": error_type,
        "actual": actual,
        "expected": expected,
        "rationale": rationale,
        "confidence": confidence,
    }
    if extra_fields:
        result.update(extra_fields)
    return result


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


def _resolve_weighted_numeric_scoring_mode(metric_config: dict[str, Any]) -> str:
    scoring_mode = metric_config.get("scoring_mode")
    if scoring_mode is None:
        for raw_field in metric_config.get("fields", []):
            if isinstance(raw_field, Mapping) and "tolerance" in raw_field:
                return "tolerance_match"
        return "linear_decay"
    if scoring_mode not in {"linear_decay", "tolerance_match"}:
        raise bad_request(
            "weighted_numeric_fields_accuracy scoring_mode must be "
            "'linear_decay' or 'tolerance_match'"
        )
    return scoring_mode


def _parse_weighted_numeric_field_configs(
    metric_config: dict[str, Any],
    scoring_mode: str,
) -> list[dict[str, Any]]:
    raw_fields = metric_config.get("fields")
    if not isinstance(raw_fields, list) or not raw_fields:
        raise bad_request("weighted_numeric_fields_accuracy requires a non-empty fields list")

    parsed_fields: list[dict[str, Any]] = []
    for raw_field in raw_fields:
        if not isinstance(raw_field, Mapping):
            raise bad_request("weighted_numeric_fields_accuracy field config must be an object")
        field_name = raw_field.get("name")
        if not isinstance(field_name, str) or not field_name.strip():
            raise bad_request("weighted_numeric_fields_accuracy field name must be a non-empty string")
        weight = raw_field.get("weight", 1.0)
        if not _is_numeric_value(weight) or float(weight) <= 0:
            raise bad_request("weighted_numeric_fields_accuracy field weight must be a positive number")
        parsed_field = {
            "name": field_name,
            "weight": float(weight),
        }
        if scoring_mode == "linear_decay":
            scale = raw_field.get("scale")
            if not _is_numeric_value(scale) or float(scale) <= 0:
                raise bad_request(
                    "weighted_numeric_fields_accuracy field scale must be a positive number"
                )
            parsed_field["scale"] = float(scale)
        else:
            tolerance = raw_field.get("tolerance", 0.0)
            if not _is_numeric_value(tolerance) or float(tolerance) < 0:
                raise bad_request(
                    "weighted_numeric_fields_accuracy field tolerance must be "
                    "a non-negative number"
                )
            parsed_field["tolerance"] = float(tolerance)
        parsed_fields.append(parsed_field)

    return parsed_fields


def _score_weighted_numeric_field_difference(
    *,
    difference: float,
    config: dict[str, Any],
    scoring_mode: str,
) -> float:
    if scoring_mode == "linear_decay":
        return max(0.0, 1.0 - difference / config["scale"])
    return 1.0 if difference <= config["tolerance"] else 0.0


def _build_weighted_numeric_field_score(
    *,
    config: dict[str, Any],
    expected_value: Any,
    actual_value: Any,
    score: float,
    difference: float | None,
    field_error_type: str | None,
) -> dict[str, Any]:
    field_score = {
        "name": config["name"],
        "weight": config["weight"],
        "expected": expected_value,
        "actual": actual_value,
        "difference": difference,
        "score": score,
        "field_error_type": field_error_type,
    }
    if "scale" in config:
        field_score["scale"] = config["scale"]
    if "tolerance" in config:
        field_score["tolerance"] = config["tolerance"]
    return field_score


def _resolve_weighted_numeric_error_type(
    field_scores: list[dict[str, Any]],
    correct: bool,
) -> str | None:
    if correct:
        return None
    field_error_types = [item.get("field_error_type") for item in field_scores]
    if "missing_field" in field_error_types:
        return "missing_field"
    if "non_numeric_field" in field_error_types:
        return "non_numeric_field"
    return "semantic_mismatch"


def _is_numeric_value(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
