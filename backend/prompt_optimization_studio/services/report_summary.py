import json
from typing import Any

from prompt_optimization_studio.services.openai_client import openai_client_service


def generate_report_summary(
    *,
    report_type: str,
    summary_payload: dict[str, Any],
    warnings: list[str],
    failures: list[dict[str, Any]],
    model_name: str | None,
) -> str:
    fallback = build_fallback_summary(
        report_type=report_type,
        summary_payload=summary_payload,
        warnings=warnings,
        failures=failures,
    )
    if not openai_client_service.configured or not model_name:
        return fallback

    resolved_model = model_name.split("/", 1)[1] if model_name.startswith("openai/") else model_name
    prompt = (
        f"Write a concise executive summary for a {report_type} report.\n"
        f"Metrics summary:\n{json.dumps(summary_payload, ensure_ascii=False, indent=2)}\n\n"
        f"Warnings:\n{json.dumps(warnings, ensure_ascii=False, indent=2)}\n\n"
        f"Representative failures:\n{json.dumps(failures[:5], ensure_ascii=False, indent=2)}\n\n"
        "Keep it short, concrete, and mention reliability risks."
    )
    try:
        return openai_client_service.generate_text(model=resolved_model, prompt=prompt, temperature=0.2).strip()
    except Exception:
        return fallback


def build_fallback_summary(
    *,
    report_type: str,
    summary_payload: dict[str, Any],
    warnings: list[str],
    failures: list[dict[str, Any]],
) -> str:
    score_bits = []
    if summary_payload.get("baseline_score") is not None:
        score_bits.append(f"baseline={summary_payload['baseline_score']:.3f}")
    if summary_payload.get("optimized_score") is not None:
        score_bits.append(f"optimized={summary_payload['optimized_score']:.3f}")
    if summary_payload.get("delta") is not None:
        score_bits.append(f"delta={summary_payload['delta']:.3f}")
    score_text = ", ".join(score_bits) if score_bits else "no score available"
    warning_text = "; ".join(warnings[:3]) if warnings else "no major warnings recorded"
    failure_text = f"{len(failures)} failures highlighted" if failures else "no highlighted failures"
    return (
        f"{report_type.capitalize()} summary: {score_text}. "
        f"Reliability notes: {warning_text}. "
        f"Observed outcome: {failure_text}."
    )
