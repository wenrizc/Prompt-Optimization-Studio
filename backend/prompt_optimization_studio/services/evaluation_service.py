from dataclasses import dataclass
from statistics import mean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from prompt_optimization_studio.core.exceptions import bad_request, not_found
from prompt_optimization_studio.models.dataset import Dataset, DatasetExample
from prompt_optimization_studio.models.evaluation import Evaluation
from prompt_optimization_studio.models.project import Project
from prompt_optimization_studio.models.prompt import Prompt
from prompt_optimization_studio.services.artifact_service import write_owner_artifact
from prompt_optimization_studio.services.dataset_service import refresh_dataset_quality_summary
from prompt_optimization_studio.services.dspy_program_factory import (
    build_dataset_bundle,
    build_program,
    dump_program_state,
    parse_prediction_output,
    strip_internal_prediction_fields,
)
from prompt_optimization_studio.services.dspy_runtime import configure_runtime
from prompt_optimization_studio.services.job_service import add_run_log, create_job, utcnow
from prompt_optimization_studio.services.metric_factory import score_metric
from prompt_optimization_studio.services.report_summary import generate_report_summary
from prompt_optimization_studio.services.runtime_service import collect_package_versions


@dataclass
class EvaluationExecutionResult:
    score: float
    report: dict[str, Any]
    predictions: list[dict[str, Any]]
    warnings: list[str]


def create_evaluation_and_job(
    db: Session,
    project_id: int,
    dataset_id: int,
    prompt_id: int,
    metric_config_json: dict[str, Any],
    model_config_json: dict[str, Any],
    random_seed: int,
) -> Evaluation:
    project = db.get(Project, project_id)
    if project is None:
        raise not_found(f"Project {project_id} not found")
    dataset = db.get(Dataset, dataset_id)
    if dataset is None or dataset.project_id != project_id:
        raise not_found(f"Dataset {dataset_id} not found in project {project_id}")
    prompt = db.get(Prompt, prompt_id)
    if prompt is None or prompt.project_id != project_id:
        raise not_found(f"Prompt {prompt_id} not found in project {project_id}")

    split_snapshot = freeze_dataset_split_snapshot(db, dataset)
    prompt_snapshot = freeze_prompt_snapshot(prompt)
    validate_evaluation_inputs(split_snapshot, prompt_snapshot, metric_config_json)

    evaluation = Evaluation(
        project_id=project_id,
        dataset_id=dataset_id,
        prompt_id=prompt_id,
        status="queued",
        progress=0,
        metric_config_json=metric_config_json,
        model_config_json=model_config_json,
        prompt_snapshot_json=prompt_snapshot,
        dataset_split_snapshot_json=split_snapshot,
        package_versions_json=collect_package_versions(),
        random_seed=random_seed,
        artifact_dir=f"artifacts/evaluations/{dataset_id}",
    )
    db.add(evaluation)
    db.flush()

    create_job(
        db=db,
        job_type="evaluation",
        target_type="evaluation",
        target_id=evaluation.id,
        payload_json={"evaluation_id": evaluation.id},
        idempotency_key=f"evaluation:{evaluation.id}",
    )
    add_run_log(db, "evaluation", evaluation.id, "info", "Evaluation queued")
    db.commit()
    db.refresh(evaluation)
    return evaluation


def execute_evaluation(db: Session, evaluation: Evaluation) -> EvaluationExecutionResult:
    dataset = db.get(Dataset, evaluation.dataset_id)
    prompt = db.get(Prompt, evaluation.prompt_id)
    if dataset is None or prompt is None:
        raise bad_request("evaluation dependencies were deleted")

    refresh_dataset_quality_summary(db, dataset)
    examples = list(
        db.scalars(select(DatasetExample).where(DatasetExample.dataset_id == dataset.id).order_by(DatasetExample.id.asc()))
    )
    test_examples = [
        example
        for example in examples
        if example.split in {"test", "dev", "train"}
        and example.quality_status != "rejected"
    ]
    if not test_examples:
        raise bad_request("dataset has no eligible examples for evaluation")
    validate_examples_against_output_schema(
        examples=test_examples,
        output_schema_json=evaluation.prompt_snapshot_json.get("output_schema_json") or {},
    )

    metric_name = evaluation.metric_config_json.get("metric", "json_field_accuracy")
    field_name = evaluation.metric_config_json.get("field")
    runtime = configure_runtime(evaluation.model_config_json)
    program = build_program(evaluation.prompt_snapshot_json)
    predictions: list[dict[str, Any]] = []
    scores: list[float] = []
    warnings = list(dataset.quality_summary_json.get("warnings", []))
    bundle = build_dataset_bundle(test_examples, evaluation.prompt_snapshot_json)
    evaluation_examples = bundle.testset if bundle.testset else bundle.all_examples

    for dsp_example in evaluation_examples:
        prediction = generate_prediction(
            runtime=runtime,
            program=program,
            dsp_example=dsp_example,
            output_schema_json=evaluation.prompt_snapshot_json.get("output_schema_json") or {},
        )
        expected_output_json = dsp_example.expected_output_json
        metric_result = score_metric(
            metric_name,
            prediction,
            expected_output_json,
            field_name,
            evaluation.metric_config_json,
        )
        scores.append(metric_result["score"])
        sanitized_prediction = strip_internal_prediction_fields(prediction)
        predictions.append(
            {
                "example_id": dsp_example.example_id,
                "split": dsp_example.split,
                "input_json": {"text": dsp_example.text},
                "expected_output_json": expected_output_json,
                "prediction": sanitized_prediction,
                "score": metric_result["score"],
                "correct": metric_result["correct"],
                "error_type": metric_result["error_type"],
                "rationale": metric_result.get("rationale"),
                "confidence": metric_result.get("confidence"),
            }
        )

    overall_score = mean(scores) if scores else 0.0
    report = build_evaluation_report(
        evaluation=evaluation,
        dataset=dataset,
        metric_name=metric_name,
        predictions=predictions,
        warnings=warnings,
        overall_score=overall_score,
        program_state=dump_program_state(program),
    )
    return EvaluationExecutionResult(
        score=overall_score,
        report=report,
        predictions=predictions,
        warnings=warnings,
    )


def finalize_evaluation_success(db: Session, evaluation: Evaluation, result: EvaluationExecutionResult) -> None:
    evaluation.status = "succeeded"
    evaluation.progress = 100
    evaluation.score = result.score
    evaluation.finished_at = utcnow()
    evaluation.error_message = None
    evaluation.artifact_dir = f"artifacts/evaluations/{evaluation.id}"
    db.add(evaluation)

    write_owner_artifact(db, "evaluation", evaluation.id, "report", "report.json", result.report)
    write_owner_artifact(db, "evaluation", evaluation.id, "predictions", "predictions.json", result.predictions)
    add_run_log(db, "evaluation", evaluation.id, "info", "Evaluation completed", {"score": result.score})
    db.flush()


def finalize_evaluation_failure(db: Session, evaluation: Evaluation, error_message: str) -> None:
    evaluation.status = "failed"
    evaluation.error_message = error_message
    evaluation.finished_at = utcnow()
    db.add(evaluation)
    add_run_log(db, "evaluation", evaluation.id, "error", error_message)
    db.flush()


def freeze_prompt_snapshot(prompt: Prompt) -> dict[str, Any]:
    return {
        "prompt_id": prompt.id,
        "name": prompt.name,
        "version": prompt.version,
        "system_prompt": prompt.system_prompt,
        "user_template": prompt.user_template,
        "output_schema_json": prompt.output_schema_json,
    }


def freeze_dataset_split_snapshot(db: Session, dataset: Dataset) -> dict[str, Any]:
    examples = list(
        db.scalars(select(DatasetExample).where(DatasetExample.dataset_id == dataset.id).order_by(DatasetExample.id.asc()))
    )
    return {
        "dataset_id": dataset.id,
        "splits": {
            split_name: [example.id for example in examples if example.split == split_name and example.quality_status != "rejected"]
            for split_name in ("train", "dev", "test", "unassigned")
        },
        "quality_summary_json": dataset.quality_summary_json,
    }


def validate_evaluation_inputs(
    split_snapshot: dict[str, Any],
    prompt_snapshot: dict[str, Any] | None = None,
    metric_config: dict[str, Any] | None = None,
) -> None:
    split_lengths = {name: len(ids) for name, ids in split_snapshot["splits"].items()}
    if sum(split_lengths.values()) == 0:
        raise bad_request("dataset has no usable examples")
    quality_summary = split_snapshot.get("quality_summary_json", {})
    if quality_summary.get("cross_split_duplicate_count", 0) > 0:
        raise bad_request("dataset contains duplicates across splits; resolve leakage before running evaluations")
    if prompt_snapshot and metric_config:
        validate_metric_against_prompt_schema(prompt_snapshot, metric_config)


def validate_metric_against_prompt_schema(prompt_snapshot: dict[str, Any], metric_config: dict[str, Any]) -> None:
    metric_name = metric_config.get("metric", "json_field_accuracy")
    output_schema_json = prompt_snapshot.get("output_schema_json") or {}
    properties = output_schema_json.get("properties") or {}
    field_name = metric_config.get("field")

    if metric_name in {"json_field_accuracy", "contains", "f1_token", "llm_judge", "gepa_feedback_metric"}:
        if field_name is None:
            field_name = next(iter(properties.keys()), None)
        if field_name is None:
            raise bad_request(f"{metric_name} requires a target field in the prompt output schema")
        if properties and field_name not in properties:
            raise bad_request(f"metric field '{field_name}' is not present in the prompt output schema")


def generate_prediction(
    runtime,
    program,
    dsp_example,
    output_schema_json: dict[str, Any],
) -> dict[str, Any]:
    if runtime.provider == "mock":
        return dict(dsp_example.expected_output_json)

    prediction = program(text=dsp_example.text)
    answer = getattr(prediction, "answer", "")
    return parse_prediction_output(output_schema_json, answer)


def validate_examples_against_output_schema(
    *,
    examples: list[DatasetExample],
    output_schema_json: dict[str, Any],
) -> None:
    schema_type = output_schema_json.get("type")
    properties = output_schema_json.get("properties") or {}
    required = output_schema_json.get("required") or []

    for example in examples:
        payload = example.expected_output_json
        if schema_type == "object":
            if not isinstance(payload, dict):
                raise bad_request(f"example {example.id} expected_output_json must be an object")
            missing_fields = [field for field in required if field not in payload]
            if missing_fields:
                joined = ", ".join(missing_fields)
                raise bad_request(f"example {example.id} is missing required output fields: {joined}")
            for field_name, field_schema in properties.items():
                if field_name in payload and not value_matches_schema(payload[field_name], field_schema):
                    raise bad_request(f"example {example.id} has invalid value for output field '{field_name}'")
        elif schema_type == "string" and "answer" in payload and not isinstance(payload["answer"], str):
            raise bad_request(f"example {example.id} answer must be a string")


def value_matches_schema(value: Any, schema: dict[str, Any]) -> bool:
    enum_values = schema.get("enum")
    if enum_values and value not in enum_values:
        return False
    schema_type = schema.get("type")
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if schema_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if schema_type == "boolean":
        return isinstance(value, bool)
    if schema_type == "array":
        return isinstance(value, list)
    if schema_type == "object":
        return isinstance(value, dict)
    return True


def build_evaluation_report(
    evaluation: Evaluation,
    dataset: Dataset,
    metric_name: str,
    predictions: list[dict[str, Any]],
    warnings: list[str],
    overall_score: float,
    program_state: dict[str, Any],
) -> dict[str, Any]:
    summary = {
        "baseline_score": overall_score,
        "optimized_score": None,
        "delta": None,
        "metric": metric_name,
        "evaluated_examples": len(predictions),
    }
    failed_examples = [item for item in predictions if not item["correct"]]
    executive_summary = generate_report_summary(
        report_type="evaluation",
        summary_payload=summary,
        warnings=warnings,
        failures=failed_examples,
        model_name=evaluation.model_config_json.get("model"),
    )
    return {
        "summary": summary,
        "executive_summary": executive_summary,
        "dataset": build_dataset_section(dataset, evaluation.dataset_split_snapshot_json),
        "metric": {
            "name": metric_name,
            "config": evaluation.metric_config_json,
            "model": evaluation.model_config_json,
        },
        "score_breakdown": {
            "by_split": aggregate_scores(predictions, "split"),
            "by_error_type": aggregate_scores(predictions, "error_type"),
        },
        "failed_examples": failed_examples,
        "warnings": warnings,
        "results": predictions,
        "artifacts": [
            {"artifact_type": "report", "file_name": "report.json"},
            {"artifact_type": "predictions", "file_name": "predictions.json"},
        ],
        "program_state": program_state,
    }


def build_dataset_section(dataset: Dataset, split_snapshot: dict[str, Any]) -> dict[str, Any]:
    quality_summary = dataset.quality_summary_json or split_snapshot.get("quality_summary_json", {})
    return {
        "dataset_id": dataset.id,
        "name": dataset.name,
        "source_type": dataset.source_type,
        "trust_level": quality_summary.get("trust_level"),
        "split_counts": quality_summary.get("split_counts", {}),
        "quality_counts": quality_summary.get("quality_counts", {}),
        "source_counts": quality_summary.get("source_counts", {}),
        "synthetic_example_count": quality_summary.get("synthetic_example_count", 0),
        "real_example_count": quality_summary.get("real_example_count", 0),
        "label_distribution": quality_summary.get("label_distribution", {}),
    }


def aggregate_scores(predictions: list[dict[str, Any]], field_name: str) -> list[dict[str, Any]]:
    groups: dict[str, list[float]] = {}
    for item in predictions:
        key = item.get(field_name) or "none"
        groups.setdefault(str(key), []).append(float(item.get("score", 0.0)))
    return [
        {"name": key, "count": len(values), "avg_score": mean(values) if values else 0.0}
        for key, values in sorted(groups.items())
    ]
