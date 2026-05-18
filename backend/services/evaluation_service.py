"""评估执行服务。

负责创建评估任务、执行模型预测、计算指标分数并生成评估报告。
"""

from dataclasses import dataclass
from statistics import mean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.exceptions import bad_request, not_found
from backend.models.dataset import Dataset, DatasetExample
from backend.models.evaluation import Evaluation
from backend.models.project import Project
from backend.models.prompt import Prompt
from backend.services.artifact_service import write_owner_artifact
from backend.services.dataset_service import refresh_dataset_quality_summary
from backend.services.dspy_program_factory import (
    build_dataset_bundle,
    build_program,
    dump_program_state,
    normalize_input_payload,
    parse_prediction_output,
    strip_internal_prediction_fields,
)
from backend.services.dspy_runtime import configure_runtime
from backend.services.job_service import add_run_log, create_job, utcnow
from backend.services.metric_factory import score_metric
from backend.services.report_summary import generate_report_summary
from backend.services.run_defaults import (
    build_default_model_config,
    resolve_project_metric_config,
)
from backend.services.runtime_service import collect_package_versions
from backend.services.validators import get_required_input_fields, get_signature_input_fields


@dataclass
class EvaluationExecutionResult:
    """评估执行结果容器, 包含分数、报告、预测和警告。"""

    score: float
    report: dict[str, Any]
    predictions: list[dict[str, Any]]
    warnings: list[str]


def create_evaluation_and_job(
    db: Session,
    project_id: int,
    dataset_id: int,
    prompt_id: int,
) -> Evaluation:
    """创建评估记录并提交后台作业。

    Args:
        db: 数据库会话。
        project_id: 项目主键。
        dataset_id: 数据集主键。
        prompt_id: 提示词主键。
    Returns:
        创建的 Evaluation 数据库记录。
    """
    project = db.get(Project, project_id)
    if project is None:
        raise not_found(f"Project {project_id} not found")
    dataset = db.get(Dataset, dataset_id)
    if dataset is None or dataset.project_id != project_id:
        raise not_found(f"Dataset {dataset_id} not found in project {project_id}")
    prompt = db.get(Prompt, prompt_id)
    if prompt is None or prompt.project_id != project_id:
        raise not_found(f"Prompt {prompt_id} not found in project {project_id}")

    metric_config_json = resolve_project_metric_config(project.default_metric_config_json)
    model_config_json = build_default_model_config()
    split_snapshot = freeze_dataset_split_snapshot(db, dataset)
    prompt_snapshot = freeze_prompt_snapshot(prompt, project)
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
        random_seed=None,
        artifact_dir=None,
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
    """执行评估流程, 包含预测生成、指标计算和报告构建。

    Args:
        db: 数据库会话。
        evaluation: 评估记录。

    Returns:
        包含分数、报告、预测和警告的执行结果。
    """
    dataset, test_examples = _load_evaluation_inputs(db, evaluation)
    metric_name = evaluation.metric_config_json.get("metric", "json_field_accuracy")
    field_name = evaluation.metric_config_json.get("field")
    runtime = configure_runtime(evaluation.model_config_json)
    program = build_program(evaluation.prompt_snapshot_json)

    warnings = list(dataset.quality_summary_json.get("warnings", []))
    bundle = build_dataset_bundle(test_examples, evaluation.prompt_snapshot_json)
    evaluation_examples = bundle.testset if bundle.testset else bundle.all_examples
    predictions, scores = _run_evaluation_loop(
        runtime=runtime,
        program=program,
        evaluation_examples=evaluation_examples,
        metric_name=metric_name,
        field_name=field_name,
        metric_config=evaluation.metric_config_json,
        output_schema_json=evaluation.prompt_snapshot_json.get("output_schema_json") or {},
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


def _load_evaluation_inputs(
    db: Session, evaluation: Evaluation
) -> tuple[Dataset, list[DatasetExample]]:
    dataset = db.get(Dataset, evaluation.dataset_id)
    prompt = db.get(Prompt, evaluation.prompt_id)
    if dataset is None or prompt is None:
        raise bad_request("evaluation dependencies were deleted")

    refresh_dataset_quality_summary(db, dataset)
    examples = list(
        db.scalars(
            select(DatasetExample)
            .where(DatasetExample.dataset_id == dataset.id)
            .order_by(DatasetExample.id.asc())
        )
    )
    test_examples = [
        ex for ex in examples
        if ex.split in {"test", "dev", "train"}
    ]
    if not test_examples:
        raise bad_request("dataset has no eligible examples for evaluation")
    validate_examples_against_output_schema(
        examples=test_examples,
        output_schema_json=evaluation.prompt_snapshot_json.get("output_schema_json") or {},
    )
    validate_examples_against_input_schema(
        examples=test_examples,
        input_schema_json=evaluation.prompt_snapshot_json.get("input_schema_json") or {},
    )
    return dataset, test_examples


def _run_evaluation_loop(
    *,
    runtime,
    program,
    evaluation_examples,
    metric_name: str,
    field_name: str | None,
    metric_config: dict[str, Any],
    output_schema_json: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[float]]:
    predictions: list[dict[str, Any]] = []
    scores: list[float] = []

    for dsp_example in evaluation_examples:
        prediction = generate_prediction(
            runtime=runtime,
            program=program,
            dsp_example=dsp_example,
            output_schema_json=output_schema_json,
        )
        metric_result = score_metric(
            metric_name, prediction, dsp_example.expected_output_json,
            field_name, metric_config,
        )
        scores.append(metric_result["score"])
        predictions.append({
            "example_id": dsp_example.example_id,
            "split": dsp_example.split,
            "raw_input_json": dsp_example.raw_input_json,
            "rendered_input_text": dsp_example.rendered_input_text,
            "expected_output_json": dsp_example.expected_output_json,
            "prediction": strip_internal_prediction_fields(prediction),
            "score": metric_result["score"],
            "correct": metric_result["correct"],
            "error_type": metric_result["error_type"],
            "rationale": metric_result.get("rationale"),
            "confidence": metric_result.get("confidence"),
            "field_scores": metric_result.get("field_scores"),
        })

    return predictions, scores


def finalize_evaluation_success(
    db: Session, evaluation: Evaluation, result: EvaluationExecutionResult
) -> None:
    """将评估标记为成功并持久化制品。"""
    evaluation.status = "succeeded"
    evaluation.progress = 100
    evaluation.score = result.score
    evaluation.finished_at = utcnow()
    evaluation.error_message = None
    evaluation.artifact_dir = f"artifacts/evaluations/{evaluation.id}"
    db.add(evaluation)

    write_owner_artifact(db, "evaluation", evaluation.id, "report", "report.json", result.report)
    write_owner_artifact(
        db, "evaluation", evaluation.id, "predictions", "predictions.json", result.predictions
    )
    add_run_log(
        db, "evaluation", evaluation.id, "info", "Evaluation completed", {"score": result.score}
    )
    db.flush()


def finalize_evaluation_failure(db: Session, evaluation: Evaluation, error_message: str) -> None:
    """将评估标记为失败并记录错误信息。"""
    evaluation.status = "failed"
    evaluation.error_message = error_message
    evaluation.finished_at = utcnow()
    db.add(evaluation)
    add_run_log(db, "evaluation", evaluation.id, "error", error_message)
    db.flush()


def freeze_prompt_snapshot(prompt: Prompt, project: Project) -> dict[str, Any]:
    """冻结提示词的快照, 用于评估时的不可变引用。"""
    return {
        "prompt_id": prompt.id,
        "name": prompt.name,
        "version": prompt.version,
        "system_prompt": prompt.system_prompt,
        "user_template": prompt.user_template,
        "input_schema_json": project.input_schema_json,
        "output_schema_json": prompt.output_schema_json,
    }


def freeze_dataset_split_snapshot(db: Session, dataset: Dataset) -> dict[str, Any]:
    """冻结数据集划分快照, 记录各划分中的样本 ID。"""
    examples = list(
        db.scalars(
            select(DatasetExample)
            .where(DatasetExample.dataset_id == dataset.id)
            .order_by(DatasetExample.id.asc())
        )
    )
    return {
        "dataset_id": dataset.id,
        "splits": {
            split_name: [
                example.id
                for example in examples
                if example.split == split_name
            ]
            for split_name in ("train", "dev", "test", "unassigned")
        },
        "quality_summary_json": dataset.quality_summary_json,
    }


def validate_evaluation_inputs(
    split_snapshot: dict[str, Any],
    prompt_snapshot: dict[str, Any] | None = None,
    metric_config: dict[str, Any] | None = None,
) -> None:
    """校验评估输入的合法性, 包括样本可用性和跨划分重复检测。"""
    split_lengths = {name: len(ids) for name, ids in split_snapshot["splits"].items()}
    if sum(split_lengths.values()) == 0:
        raise bad_request("dataset has no usable examples")
    quality_summary = split_snapshot.get("quality_summary_json", {})
    if quality_summary.get("cross_split_duplicate_count", 0) > 0:
        raise bad_request(
            "dataset contains duplicates across splits; resolve leakage before running evaluations"
        )
    if prompt_snapshot and metric_config:
        validate_metric_against_prompt_schema(prompt_snapshot, metric_config)


def validate_metric_against_prompt_schema(
    prompt_snapshot: dict[str, Any], metric_config: dict[str, Any]
) -> None:
    """校验指标配置中的字段是否与提示词输出 schema 兼容。"""
    metric_name = metric_config.get("metric", "json_field_accuracy")
    output_schema_json = prompt_snapshot.get("output_schema_json") or {}
    properties = output_schema_json.get("properties") or {}
    field_name = metric_config.get("field")

    if metric_name == "weighted_numeric_fields_accuracy":
        raw_fields = metric_config.get("fields")
        if not isinstance(raw_fields, list) or not raw_fields:
            raise bad_request("weighted_numeric_fields_accuracy requires a non-empty fields list")
        scoring_mode = metric_config.get("scoring_mode")
        if scoring_mode is None:
            scoring_mode = (
                "tolerance_match"
                if any(isinstance(raw_field, dict) and "tolerance" in raw_field for raw_field in raw_fields)
                else "linear_decay"
            )
        if scoring_mode not in {"linear_decay", "tolerance_match"}:
            raise bad_request(
                "weighted_numeric_fields_accuracy scoring_mode must be "
                "'linear_decay' or 'tolerance_match'"
            )
        pass_threshold = metric_config.get("pass_threshold", 1.0)
        if not isinstance(pass_threshold, (int, float)) or isinstance(pass_threshold, bool):
            raise bad_request("weighted_numeric_fields_accuracy pass_threshold must be numeric")
        if not 0.0 <= float(pass_threshold) <= 1.0:
            raise bad_request(
                "weighted_numeric_fields_accuracy pass_threshold must be between 0 and 1"
            )
        for raw_field in raw_fields:
            if not isinstance(raw_field, dict):
                raise bad_request("weighted_numeric_fields_accuracy field config must be an object")
            target_field = raw_field.get("name")
            if not isinstance(target_field, str) or not target_field.strip():
                raise bad_request(
                    "weighted_numeric_fields_accuracy field name must be a non-empty string"
                )
            if properties and target_field not in properties:
                raise bad_request(
                    f"metric field '{target_field}' is not present in the prompt output schema"
                )
            field_schema = properties.get(target_field) or {}
            field_type = field_schema.get("type")
            if field_type not in {"number", "integer"}:
                raise bad_request(
                    f"metric field '{target_field}' must be numeric in the prompt output schema"
                )
            weight = raw_field.get("weight", 1.0)
            if (
                not isinstance(weight, (int, float))
                or isinstance(weight, bool)
                or float(weight) <= 0
            ):
                raise bad_request(
                    f"metric field '{target_field}' weight must be a positive number"
                )
            if scoring_mode == "linear_decay":
                scale = raw_field.get("scale")
                if (
                    not isinstance(scale, (int, float))
                    or isinstance(scale, bool)
                    or float(scale) <= 0
                ):
                    raise bad_request(
                        f"metric field '{target_field}' scale must be a positive number"
                    )
            else:
                tolerance = raw_field.get("tolerance", 0.0)
                if (
                    not isinstance(tolerance, (int, float))
                    or isinstance(tolerance, bool)
                    or float(tolerance) < 0
                ):
                    raise bad_request(
                        f"metric field '{target_field}' tolerance must be a non-negative number"
                    )
        return

    if metric_name in {
        "json_field_accuracy",
        "contains",
        "f1_token",
        "llm_judge",
        "gepa_feedback_metric",
    }:
        if field_name is None:
            field_name = next(iter(properties.keys()), None)
        if field_name is None:
            raise bad_request(f"{metric_name} requires a target field in the prompt output schema")
        if properties and field_name not in properties:
            raise bad_request(
                f"metric field '{field_name}' is not present in the prompt output schema"
            )


def generate_prediction(
    runtime,
    program,
    dsp_example,
    output_schema_json: dict[str, Any],
) -> dict[str, Any]:
    """对单个样本执行模型预测并解析输出。

    Args:
        runtime: DSPy 运行时句柄。
        program: DSPy 预测模块。
        dsp_example: DSPy Example 对象。
        output_schema_json: 输出 schema 定义。

    Returns:
        解析后的预测结果字典。
    """
    if runtime.provider == "mock":
        return dict(dsp_example.expected_output_json)

    prediction = program(**dsp_example.inputs().toDict())
    answer = getattr(prediction, "answer", "")
    return parse_prediction_output(output_schema_json, answer)


def validate_examples_against_output_schema(
    *,
    examples: list[DatasetExample],
    output_schema_json: dict[str, Any],
) -> None:
    """校验样本的期望输出是否符合输出 schema 定义。"""
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
                raise bad_request(
                    f"example {example.id} is missing required output fields: {joined}"
                )
            for field_name, field_schema in properties.items():
                if field_name in payload and not value_matches_schema(
                    payload[field_name], field_schema
                ):
                    raise bad_request(
                        f"example {example.id} has invalid value for output field '{field_name}'"
                    )
        elif (
            schema_type == "string"
            and "answer" in payload
            and not isinstance(payload["answer"], str)
        ):
            raise bad_request(f"example {example.id} answer must be a string")


def validate_examples_against_input_schema(
    *,
    examples: list[DatasetExample],
    input_schema_json: dict[str, Any],
) -> None:
    """校验样本输入是否符合当前支持的输入 schema 边界。"""
    input_fields = get_signature_input_fields(input_schema_json)
    required_fields = get_required_input_fields(input_schema_json)

    for example in examples:
        normalize_input_payload(
            example.input_json,
            input_fields=input_fields,
            required_fields=required_fields,
            example_id=example.id,
        )


def value_matches_schema(value: Any, schema: dict[str, Any]) -> bool:
    """判断值是否匹配 JSON Schema 定义。"""
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
    """构建完整的评估报告, 包含摘要、指标明细和失败样例。

    Args:
        evaluation: 评估记录。
        dataset: 关联数据集。
        metric_name: 指标名称。
        predictions: 预测结果列表。
        warnings: 警告信息列表。
        overall_score: 总体得分。
        program_state: DSPy 程序状态。

    Returns:
        完整的评估报告字典。
    """
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
    """构建报告中的数据集概要信息。"""
    quality_summary = dataset.quality_summary_json or split_snapshot.get("quality_summary_json", {})
    return {
        "dataset_id": dataset.id,
        "name": dataset.name,
        "source_type": dataset.source_type,
        "trust_level": quality_summary.get("trust_level"),
        "split_counts": quality_summary.get("split_counts", {}),
        "source_counts": quality_summary.get("source_counts", {}),
        "synthetic_example_count": quality_summary.get("synthetic_example_count", 0),
        "real_example_count": quality_summary.get("real_example_count", 0),
        "label_distribution": quality_summary.get("label_distribution", {}),
    }


def aggregate_scores(predictions: list[dict[str, Any]], field_name: str) -> list[dict[str, Any]]:
    """按指定字段对预测结果进行分组统计平均分。"""
    groups: dict[str, list[float]] = {}
    for item in predictions:
        key = item.get(field_name) or "none"
        groups.setdefault(str(key), []).append(float(item.get("score", 0.0)))
    return [
        {"name": key, "count": len(values), "avg_score": mean(values) if values else 0.0}
        for key, values in sorted(groups.items())
    ]
