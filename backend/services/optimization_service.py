"""提示词优化执行服务。

负责创建优化运行、执行 DSPy 编译器、对比基线与优化后的性能, 并生成报告。
"""

from statistics import mean
from typing import Any

from dspy.teleprompt.gepa.gepa_utils import ScoreWithFeedback
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.constants import FEEDBACK_RICH_METRICS
from backend.core.exceptions import bad_request, not_found
from backend.models.dataset import Dataset, DatasetExample
from backend.models.optimization_run import OptimizationRun
from backend.models.project import Project
from backend.models.prompt import Prompt
from backend.services.artifact_service import write_owner_artifact
from backend.services.dspy_program_factory import (
    build_dataset_bundle,
    build_program,
    dump_program_state,
    extract_predictor_demos,
    parse_prediction_output,
    strip_internal_prediction_fields,
)
from backend.services.dspy_runtime import configure_runtime
from backend.services.evaluation_service import (
    aggregate_scores,
    build_dataset_section,
    freeze_dataset_split_snapshot,
    freeze_prompt_snapshot,
    validate_evaluation_inputs,
    validate_examples_against_input_schema,
    validate_examples_against_output_schema,
)
from backend.services.job_service import add_run_log, create_job, utcnow
from backend.services.metric_factory import score_metric
from backend.services.report_summary import generate_report_summary
from backend.services.run_defaults import (
    build_default_model_config,
    resolve_project_metric_config,
)
from backend.services.runtime_service import collect_package_versions


def create_optimization_run_and_job(
    db: Session,
    project_id: int,
    dataset_id: int,
    prompt_id: int,
    optimizer_name: str,
    optimizer_config_snapshot_json: dict[str, Any],
) -> OptimizationRun:
    """创建优化运行记录并提交后台作业。

    Args:
        db: 数据库会话。
        project_id: 项目主键。
        dataset_id: 数据集主键。
        prompt_id: 提示词主键。
        optimizer_name: 优化器名称。
        optimizer_config_snapshot_json: 优化器配置快照。
    Returns:
        创建的 OptimizationRun 记录。
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

    metric_config_snapshot_json = resolve_project_metric_config(
        project.default_metric_config_json
    )
    model_config_snapshot_json = build_default_model_config()
    split_snapshot = freeze_dataset_split_snapshot(db, dataset)
    prompt_snapshot = freeze_prompt_snapshot(prompt, project)
    validate_evaluation_inputs(split_snapshot, prompt_snapshot, metric_config_snapshot_json)
    validate_optimizer_inputs(
        optimizer_name=optimizer_name,
        split_snapshot=split_snapshot,
        metric_config_snapshot_json=metric_config_snapshot_json,
    )

    resolved_metric_threshold = resolve_metric_threshold(metric_config_snapshot_json)
    optimizer_snapshot = dict(optimizer_config_snapshot_json)
    if resolved_metric_threshold is not None:
        optimizer_snapshot.setdefault("resolved_metric_threshold", resolved_metric_threshold)

    run = OptimizationRun(
        project_id=project_id,
        dataset_id=dataset_id,
        prompt_id=prompt_id,
        optimizer_name=optimizer_name,
        status="queued",
        progress=0,
        prompt_snapshot_json=prompt_snapshot,
        dataset_split_snapshot_json=split_snapshot,
        model_config_snapshot_json=model_config_snapshot_json,
        optimizer_config_snapshot_json=optimizer_snapshot,
        metric_config_snapshot_json=metric_config_snapshot_json,
        package_versions_json=collect_package_versions(),
        random_seed=None,
        artifact_dir=None,
    )
    db.add(run)
    db.flush()

    create_job(
        db=db,
        job_type="optimization",
        target_type="optimization_run",
        target_id=run.id,
        payload_json={"optimization_run_id": run.id},
        idempotency_key=f"optimization:{run.id}",
    )
    add_run_log(db, "optimization", run.id, "info", "Optimization queued")
    db.commit()
    db.refresh(run)
    return run


def execute_optimization_run(db: Session, run: OptimizationRun) -> dict[str, Any]:
    """执行优化流程, 包含基线评估、编译、对比和报告生成。

    Args:
        db: 数据库会话。
        run: 优化运行记录。

    Returns:
        包含基线分、优化分、报告和优化后提示词的结果字典。
    """
    dataset, eligible_examples = _load_optimization_inputs(db, run)
    metric_name = run.metric_config_snapshot_json.get("metric", "json_field_accuracy")
    field_name = run.metric_config_snapshot_json.get("field")
    runtime = configure_runtime(run.model_config_snapshot_json)
    execution_mode = runtime.provider

    baseline_program = build_program(run.prompt_snapshot_json)
    bundle = build_dataset_bundle(eligible_examples, run.prompt_snapshot_json)
    optimized_program = compile_optimized_program(
        runtime=runtime,
        program=baseline_program,
        bundle=bundle,
        optimizer_name=run.optimizer_name,
        optimizer_config=run.optimizer_config_snapshot_json,
        metric_name=metric_name,
        field_name=field_name,
        output_schema_json=run.prompt_snapshot_json.get("output_schema_json") or {},
        metric_config=run.metric_config_snapshot_json,
    )
    optimization_effective = runtime.provider != "mock"
    derived_prompt_candidate = None
    derived_prompt_diff = None
    if optimization_effective:
        derived_prompt_candidate = build_derived_prompt_candidate(
            run.prompt_snapshot_json,
            run.optimizer_name,
            optimized_program,
        )
        derived_prompt_diff = {
            "before_system_prompt": run.prompt_snapshot_json["system_prompt"],
            "after_system_prompt": derived_prompt_candidate["system_prompt"],
            "before_user_template": run.prompt_snapshot_json["user_template"],
            "after_user_template": derived_prompt_candidate["user_template"],
        }

    eval_examples = bundle.testset if bundle.testset else bundle.all_examples
    baseline_results, optimized_results, baseline_scores, optimized_scores = (
        _run_comparative_predictions(
            runtime=runtime,
            baseline_program=baseline_program,
            optimized_program=optimized_program,
            eval_examples=eval_examples,
            metric_name=metric_name,
            field_name=field_name,
            metric_config=run.metric_config_snapshot_json,
            output_schema_json=run.prompt_snapshot_json.get("output_schema_json") or {},
        )
    )

    baseline_score = mean(baseline_scores) if baseline_scores else 0.0
    optimized_score = mean(optimized_scores) if optimized_scores else 0.0
    summary = _build_optimization_summary(run, baseline_score, optimized_score)
    result_rows = _merge_baseline_optimized_results(baseline_results, optimized_results)
    report = _build_optimization_report(
        run=run,
        dataset=dataset,
        metric_name=metric_name,
        summary=summary,
        baseline_results=baseline_results,
        optimized_results=optimized_results,
        result_rows=result_rows,
        execution_mode=execution_mode,
        optimization_effective=optimization_effective,
        include_prompt_artifacts=derived_prompt_candidate is not None,
    )

    return {
        "baseline_score": baseline_score,
        "optimized_score": optimized_score,
        "report": report,
        "baseline_results": baseline_results,
        "optimized_results": optimized_results,
        "comparative_results": result_rows,
        "derived_prompt_candidate": derived_prompt_candidate,
        "derived_prompt_diff": derived_prompt_diff,
        "compiled_program": dump_program_state(optimized_program),
        "fewshot_demos": extract_predictor_demos(optimized_program),
    }


def _load_optimization_inputs(
    db: Session, run: OptimizationRun
) -> tuple[Dataset, list[DatasetExample]]:
    dataset = db.get(Dataset, run.dataset_id)
    if dataset is None:
        raise bad_request("dataset was deleted")

    examples = list(
        db.scalars(
            select(DatasetExample)
            .where(DatasetExample.dataset_id == run.dataset_id)
            .order_by(DatasetExample.id.asc())
        )
    )
    if not examples:
        raise bad_request("dataset has no eligible examples")
    validate_examples_against_output_schema(
        examples=examples,
        output_schema_json=run.prompt_snapshot_json.get("output_schema_json") or {},
    )
    validate_examples_against_input_schema(
        examples=examples,
        input_schema_json=run.prompt_snapshot_json.get("input_schema_json") or {},
    )
    return dataset, examples


def _run_comparative_predictions(
    *,
    runtime,
    baseline_program,
    optimized_program,
    eval_examples,
    metric_name: str,
    field_name: str | None,
    metric_config: dict[str, Any],
    output_schema_json: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[float], list[float]]:
    baseline_results: list[dict[str, Any]] = []
    optimized_results: list[dict[str, Any]] = []
    baseline_scores: list[float] = []
    optimized_scores: list[float] = []

    for dsp_example in eval_examples:
        baseline_prediction = run_program_prediction(
            runtime=runtime,
            program=baseline_program,
            dsp_example=dsp_example,
            output_schema_json=output_schema_json,
        )
        optimized_prediction = run_program_prediction(
            runtime=runtime,
            program=optimized_program,
            dsp_example=dsp_example,
            output_schema_json=output_schema_json,
        )
        baseline_metric = score_metric(
            metric_name, baseline_prediction, dsp_example.expected_output_json,
            field_name, metric_config,
        )
        optimized_metric = score_metric(
            metric_name, optimized_prediction, dsp_example.expected_output_json,
            field_name, metric_config,
        )
        baseline_scores.append(baseline_metric["score"])
        optimized_scores.append(optimized_metric["score"])
        baseline_results.append(_build_prediction_record(dsp_example, baseline_prediction, baseline_metric))
        optimized_results.append(_build_prediction_record(dsp_example, optimized_prediction, optimized_metric))

    return baseline_results, optimized_results, baseline_scores, optimized_scores


def _build_prediction_record(
    dsp_example, prediction: dict[str, Any], metric_result: dict[str, Any]
) -> dict[str, Any]:
    return {
        "example_id": dsp_example.example_id,
        "split": dsp_example.split,
        "raw_input_json": dsp_example.raw_input_json,
        "rendered_input_text": dsp_example.rendered_input_text,
        "expected_output_json": dsp_example.expected_output_json,
        "prediction": strip_internal_prediction_fields(prediction),
        "score": metric_result["score"],
        "error_type": metric_result["error_type"],
        "correct": metric_result["correct"],
        "rationale": metric_result.get("rationale"),
        "field_scores": metric_result.get("field_scores"),
    }


def _build_optimization_summary(
    run: OptimizationRun, baseline_score: float, optimized_score: float
) -> dict[str, Any]:
    return {
        "baseline_score": baseline_score,
        "optimized_score": optimized_score,
        "delta": optimized_score - baseline_score,
        "optimizer_name": run.optimizer_name,
        "metric": run.metric_config_snapshot_json.get("metric"),
    }


def _merge_baseline_optimized_results(
    baseline_results: list[dict[str, Any]], optimized_results: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        {
            "example_id": base["example_id"],
            "split": base["split"],
            "raw_input_json": base["raw_input_json"],
            "rendered_input_text": base["rendered_input_text"],
            "expected_output_json": base["expected_output_json"],
            "baseline_prediction": base["prediction"],
            "baseline_score": base["score"],
            "baseline_error_type": base["error_type"],
            "optimized_prediction": opt["prediction"],
            "optimized_score": opt["score"],
            "optimized_error_type": opt["error_type"],
            "delta": opt["score"] - base["score"],
        }
        for base, opt in zip(baseline_results, optimized_results, strict=False)
    ]


def _build_optimization_report(
    *,
    run: OptimizationRun,
    dataset: Dataset,
    metric_name: str,
    summary: dict[str, Any],
    baseline_results: list[dict[str, Any]],
    optimized_results: list[dict[str, Any]],
    result_rows: list[dict[str, Any]],
    execution_mode: str,
    optimization_effective: bool,
    include_prompt_artifacts: bool,
) -> dict[str, Any]:
    failed_examples = [row for row in result_rows if row["optimized_score"] < 1.0]
    regression_examples = [row for row in result_rows if row["delta"] < 0]
    executive_summary = generate_report_summary(
        report_type="optimization",
        summary_payload=summary,
        warnings=list(
            run.dataset_split_snapshot_json.get("quality_summary_json", {}).get("warnings", [])
        ),
        failures=regression_examples or failed_examples,
        model_name=run.model_config_snapshot_json.get("model"),
    )
    return {
        "summary": summary,
        "executive_summary": executive_summary,
        "dataset": build_dataset_section(dataset, run.dataset_split_snapshot_json),
        "metric": {
            "name": metric_name,
            "config": run.metric_config_snapshot_json,
            "model": run.model_config_snapshot_json,
        },
        "optimizer": {
            "name": run.optimizer_name,
            "config": run.optimizer_config_snapshot_json,
            "execution_mode": execution_mode,
            "optimization_effective": optimization_effective,
        },
        "score_breakdown": {
            "baseline_by_split": aggregate_scores(baseline_results, "split"),
            "optimized_by_split": aggregate_scores(optimized_results, "split"),
            "optimized_by_error_type": aggregate_scores(optimized_results, "error_type"),
        },
        "failed_examples": failed_examples,
        "regression_examples": regression_examples,
        "results": result_rows,
        "warnings": list(
            run.dataset_split_snapshot_json.get("quality_summary_json", {}).get("warnings", [])
        ),
        "artifacts": [
            {"artifact_type": "report", "file_name": "report.json"},
            {"artifact_type": "baseline_predictions", "file_name": "baseline_predictions.json"},
            {"artifact_type": "optimized_predictions", "file_name": "optimized_predictions.json"},
            {"artifact_type": "comparative_results", "file_name": "comparative_results.json"},
            {"artifact_type": "compiled_program", "file_name": "compiled_program.json"},
            {"artifact_type": "fewshot_demos", "file_name": "fewshot_demos.json"},
        ]
        + (
            [
                {
                    "artifact_type": "derived_prompt_candidate",
                    "file_name": "derived_prompt_candidate.json",
                },
                {"artifact_type": "derived_prompt_diff", "file_name": "derived_prompt_diff.json"},
            ]
            if include_prompt_artifacts
            else []
        ),
    }


def validate_optimizer_inputs(
    *,
    optimizer_name: str,
    split_snapshot: dict[str, Any],
    metric_config_snapshot_json: dict[str, Any],
) -> None:
    """校验优化器输入的前置条件, 包括数据量要求和指标兼容性。"""
    splits = split_snapshot.get("splits", {})
    train_count = len(splits.get("train", []))
    dev_count = len(splits.get("dev", []))
    test_count = len(splits.get("test", []))
    total_count = train_count + dev_count + test_count + len(splits.get("unassigned", []))

    if optimizer_name == "bootstrap_fewshot" and train_count == 0:
        raise bad_request("BootstrapFewShot requires at least one train example")
    if optimizer_name == "miprov2":
        if dev_count == 0:
            raise bad_request("MIPROv2 requires a dev split")
        if total_count < 30:
            raise bad_request("MIPROv2 requires at least 30 examples for a meaningful run")
    if optimizer_name == "gepa":
        if dev_count == 0:
            raise bad_request("GEPA requires a dev split")
        if metric_config_snapshot_json.get("metric") not in FEEDBACK_RICH_METRICS:
            raise bad_request("GEPA requires a feedback-rich metric such as gepa_feedback_metric")
        if total_count < 30:
            raise bad_request("GEPA requires at least 30 examples for a meaningful run")


def finalize_optimization_success(
    db: Session, run: OptimizationRun, result: dict[str, Any]
) -> None:
    """将优化运行标记为成功并持久化所有制品。"""
    run.status = "succeeded"
    run.progress = 100
    run.baseline_score = result["baseline_score"]
    run.optimized_score = result["optimized_score"]
    run.finished_at = utcnow()
    run.artifact_dir = f"artifacts/optimization_runs/{run.id}"
    db.add(run)

    write_owner_artifact(db, "optimization_run", run.id, "report", "report.json", result["report"])
    write_owner_artifact(
        db,
        "optimization_run",
        run.id,
        "baseline_predictions",
        "baseline_predictions.json",
        result["baseline_results"],
    )
    write_owner_artifact(
        db,
        "optimization_run",
        run.id,
        "optimized_predictions",
        "optimized_predictions.json",
        result["optimized_results"],
    )
    write_owner_artifact(
        db,
        "optimization_run",
        run.id,
        "comparative_results",
        "comparative_results.json",
        result["comparative_results"],
    )
    write_owner_artifact(
        db,
        "optimization_run",
        run.id,
        "compiled_program",
        "compiled_program.json",
        result["compiled_program"],
    )
    write_owner_artifact(
        db,
        "optimization_run",
        run.id,
        "fewshot_demos",
        "fewshot_demos.json",
        result["fewshot_demos"],
    )
    if result["derived_prompt_candidate"] is not None:
        write_owner_artifact(
            db,
            "optimization_run",
            run.id,
            "derived_prompt_candidate",
            "derived_prompt_candidate.json",
            result["derived_prompt_candidate"],
        )
    if result["derived_prompt_diff"] is not None:
        write_owner_artifact(
            db,
            "optimization_run",
            run.id,
            "derived_prompt_diff",
            "derived_prompt_diff.json",
            result["derived_prompt_diff"],
        )
    add_run_log(
        db,
        "optimization",
        run.id,
        "info",
        "Optimization completed",
        {"baseline_score": result["baseline_score"], "optimized_score": result["optimized_score"]},
    )
    db.flush()


def finalize_optimization_failure(db: Session, run: OptimizationRun, error_message: str) -> None:
    """将优化运行标记为失败并记录错误信息。"""
    run.status = "failed"
    run.error_message = error_message
    run.finished_at = utcnow()
    db.add(run)
    add_run_log(db, "optimization", run.id, "error", error_message)
    db.flush()


def build_derived_prompt_candidate(
    prompt_snapshot_json: dict[str, Any], optimizer_name: str, optimized_program
) -> dict[str, Any]:
    """根据优化后的程序构建可编辑的候选提示词。"""
    system_prompt = prompt_snapshot_json["system_prompt"]
    user_template = prompt_snapshot_json["user_template"]
    learned_instruction = getattr(getattr(optimized_program, "predict", None), "signature", None)
    learned_text = getattr(learned_instruction, "instructions", "")
    suffix = f"\n\nOptimizer note: refined by {optimizer_name}."
    if learned_text:
        suffix += f"\n\nLearned instructions:\n{learned_text}"
    return {
        **prompt_snapshot_json,
        "artifact_type": "derived_prompt_candidate",
        "export_strategy": "project_prompt_plus_compiled_instructions",
        "is_authoritative_dspy_state": False,
        "system_prompt": f"{system_prompt}{suffix}" if system_prompt else suffix.strip(),
        "user_template": user_template,
        "notes": "This prompt is derived from compiled DSPy state and remains editable.",
    }


def compile_optimized_program(
    runtime,
    program,
    bundle,
    optimizer_name: str,
    optimizer_config: dict[str, Any],
    metric_name: str,
    field_name: str | None,
    output_schema_json: dict[str, Any],
    metric_config: dict[str, Any],
):
    """使用指定的 DSPy 优化器编译程序。

    Args:
        runtime: DSPy 运行时句柄。
        program: 基线 DSPy 程序。
        bundle: 数据集分捆。
        optimizer_name: 优化器名称。
        optimizer_config: 优化器配置。
        metric_name: 指标名称。
        field_name: 目标字段名。
        output_schema_json: 输出 schema 定义。
        metric_config: 指标配置。

    Returns:
        编译后的 DSPy 程序。
    """
    if runtime.provider == "mock":
        return program

    import dspy

    metric = build_optimizer_metric(
        metric_name,
        field_name,
        output_schema_json=output_schema_json,
        metric_config=metric_config,
        feedback=(optimizer_name == "gepa"),
    )
    dispatchers = {
        "bootstrap_fewshot": _compile_bootstrap_fewshot,
        "miprov2": _compile_miprov2,
        "gepa": _compile_gepa,
    }
    dispatcher = dispatchers.get(optimizer_name)
    if dispatcher is None:
        raise bad_request(f"unsupported optimizer: {optimizer_name}")
    return dispatcher(dspy, program, bundle, optimizer_config, metric)


def _compile_bootstrap_fewshot(dspy, program, bundle, config: dict[str, Any], metric) -> Any:
    if not bundle.trainset:
        raise bad_request("BootstrapFewShot requires train split examples")
    optimizer_kwargs: dict[str, Any] = {
        "metric": metric,
        "max_bootstrapped_demos": config.get("max_bootstrapped_demos", 4),
        "max_labeled_demos": config.get("max_labeled_demos", 4),
        "max_rounds": config.get("max_rounds", 1),
    }
    if config.get("resolved_metric_threshold") is not None:
        optimizer_kwargs["metric_threshold"] = config["resolved_metric_threshold"]
    optimizer = dspy.BootstrapFewShot(
        **optimizer_kwargs,
    )
    return optimizer.compile(program, trainset=bundle.trainset)


def _compile_miprov2(dspy, program, bundle, config: dict[str, Any], metric) -> Any:
    if not bundle.trainset or not bundle.devset:
        raise bad_request("MIPROv2 requires both train and dev split examples")
    optimizer = dspy.MIPROv2(
        metric=metric,
        auto=config.get("auto", "light"),
        num_threads=config.get("num_threads"),
        max_bootstrapped_demos=config.get("max_bootstrapped_demos", 4),
        max_labeled_demos=config.get("max_labeled_demos", 4),
        seed=config.get("seed", 9),
        verbose=config.get("verbose", False),
    )
    compile_kwargs: dict[str, Any] = {
        "trainset": bundle.trainset,
        "valset": bundle.devset,
        "minibatch": config.get("minibatch", True),
        "minibatch_size": config.get("minibatch_size", 35),
        "minibatch_full_eval_steps": config.get("minibatch_full_eval_steps", 5),
    }
    if config.get("num_trials") is not None:
        compile_kwargs["num_trials"] = config["num_trials"]
    return optimizer.compile(program, **compile_kwargs)


def _compile_gepa(dspy, program, bundle, config: dict[str, Any], metric) -> Any:
    if not bundle.trainset or not bundle.devset:
        raise bad_request("GEPA requires both train and dev split examples")
    optimizer = dspy.GEPA(
        metric=metric,
        auto=config.get("auto", "light"),
        max_metric_calls=config.get("max_metric_calls"),
        num_threads=config.get("num_threads"),
        track_stats=config.get("track_stats", True),
        log_dir=config.get("log_dir"),
        seed=config.get("seed", 0),
    )
    return optimizer.compile(program, trainset=bundle.trainset, valset=bundle.devset)


def run_program_prediction(
    runtime, program, dsp_example, output_schema_json: dict[str, Any]
) -> dict[str, Any]:
    """对单个样本执行程序预测。Mock 模式下直接返回期望输出。"""
    if runtime.provider == "mock":
        return dict(dsp_example.expected_output_json)
    prediction = program(**dsp_example.inputs().toDict())
    answer = getattr(prediction, "answer", "")
    return parse_prediction_output(output_schema_json, answer)


def build_optimizer_metric(
    metric_name: str,
    field_name: str | None,
    *,
    output_schema_json: dict[str, Any],
    metric_config: dict[str, Any],
    feedback: bool = False,
):
    """构建供 DSPy 优化器使用的指标函数。

    Args:
        metric_name: 指标名称。
        field_name: 目标字段名。
        output_schema_json: 输出 schema 定义。
        metric_config: 指标配置。
        feedback: 是否返回带反馈的评分对象(用于 GEPA)。

    Returns:
        DSPy 兼容的指标函数。
    """
    def metric(gold, pred, trace=None, pred_name=None, pred_trace=None):
        parsed_prediction = parse_prediction_output(output_schema_json, getattr(pred, "answer", ""))
        result = score_metric(
            metric_name, parsed_prediction, gold.expected_output_json, field_name, metric_config
        )
        if feedback:
            feedback_text = result.get("feedback") or (
                f"Input JSON: {gold.raw_input_json}\n"
                f"Rendered prompt: {gold.rendered_input_text}\n"
                f"Expected: {gold.expected_output_json}\n"
                f"Actual: {strip_internal_prediction_fields(parsed_prediction)}\n"
                f"Error type: {result['error_type'] or 'none'}\n"
                "If wrong, adjust instructions to better match the expected structure and label."
            )
            return ScoreWithFeedback(score=float(result["score"]), feedback=feedback_text)
        return float(result["score"])

    return metric


def resolve_metric_threshold(metric_config: dict[str, Any]) -> float | None:
    """从指标配置推导 BootstrapFewShot 使用的阈值。"""
    for key in ("correct_threshold", "pass_threshold"):
        value = metric_config.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None
