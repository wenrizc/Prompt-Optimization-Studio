from statistics import mean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from prompt_optimization_studio.core.exceptions import bad_request, not_found
from prompt_optimization_studio.core.constants import FEEDBACK_RICH_METRICS
from prompt_optimization_studio.models.dataset import Dataset, DatasetExample
from prompt_optimization_studio.models.optimization_run import OptimizationRun
from prompt_optimization_studio.models.project import Project
from prompt_optimization_studio.models.prompt import Prompt
from prompt_optimization_studio.services.artifact_service import write_owner_artifact
from prompt_optimization_studio.services.dspy_program_factory import (
    build_dataset_bundle,
    build_program,
    dump_program_state,
    extract_predictor_demos,
    parse_prediction_output,
    strip_internal_prediction_fields,
)
from prompt_optimization_studio.services.dspy_runtime import configure_runtime
from prompt_optimization_studio.services.evaluation_service import (
    aggregate_scores,
    build_dataset_section,
    freeze_dataset_split_snapshot,
    freeze_prompt_snapshot,
    validate_examples_against_output_schema,
    validate_evaluation_inputs,
)
from prompt_optimization_studio.services.job_service import add_run_log, create_job, utcnow
from prompt_optimization_studio.services.metric_factory import score_metric
from dspy.teleprompt.gepa.gepa_utils import ScoreWithFeedback
from prompt_optimization_studio.services.report_summary import generate_report_summary
from prompt_optimization_studio.services.runtime_service import collect_package_versions


def create_optimization_run_and_job(
    db: Session,
    project_id: int,
    dataset_id: int,
    prompt_id: int,
    optimizer_name: str,
    metric_config_snapshot_json: dict[str, Any],
    model_config_snapshot_json: dict[str, Any],
    optimizer_config_snapshot_json: dict[str, Any],
    random_seed: int,
) -> OptimizationRun:
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
    validate_evaluation_inputs(split_snapshot, prompt_snapshot, metric_config_snapshot_json)
    validate_optimizer_inputs(
        optimizer_name=optimizer_name,
        split_snapshot=split_snapshot,
        metric_config_snapshot_json=metric_config_snapshot_json,
    )

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
        optimizer_config_snapshot_json=optimizer_config_snapshot_json,
        metric_config_snapshot_json=metric_config_snapshot_json,
        package_versions_json=collect_package_versions(),
        random_seed=random_seed,
        artifact_dir=f"artifacts/optimization_runs/{dataset_id}",
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
    dataset = db.get(Dataset, run.dataset_id)
    if dataset is None:
        raise bad_request("dataset was deleted")

    examples = list(
        db.scalars(select(DatasetExample).where(DatasetExample.dataset_id == run.dataset_id).order_by(DatasetExample.id.asc()))
    )
    eligible_examples = [example for example in examples if example.quality_status != "rejected"]
    if not eligible_examples:
        raise bad_request("dataset has no eligible examples")
    validate_examples_against_output_schema(
        examples=eligible_examples,
        output_schema_json=run.prompt_snapshot_json.get("output_schema_json") or {},
    )

    metric_name = run.metric_config_snapshot_json.get("metric", "json_field_accuracy")
    field_name = run.metric_config_snapshot_json.get("field")
    runtime = configure_runtime(run.model_config_snapshot_json)
    baseline_results: list[dict[str, Any]] = []
    optimized_results: list[dict[str, Any]] = []
    baseline_scores: list[float] = []
    optimized_scores: list[float] = []
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
    optimized_prompt = build_optimized_prompt(run.prompt_snapshot_json, run.optimizer_name, optimized_program)
    prompt_diff = {
        "before_system_prompt": run.prompt_snapshot_json["system_prompt"],
        "after_system_prompt": optimized_prompt["system_prompt"],
        "before_user_template": run.prompt_snapshot_json["user_template"],
        "after_user_template": optimized_prompt["user_template"],
    }

    eval_examples = bundle.testset if bundle.testset else bundle.all_examples
    for dsp_example in eval_examples:
        baseline_prediction = run_program_prediction(
            runtime=runtime,
            program=baseline_program,
            dsp_example=dsp_example,
            output_schema_json=run.prompt_snapshot_json.get("output_schema_json") or {},
        )
        optimized_prediction = run_program_prediction(
            runtime=runtime,
            program=optimized_program,
            dsp_example=dsp_example,
            output_schema_json=run.prompt_snapshot_json.get("output_schema_json") or {},
        )
        optimized_metric = score_metric(
            metric_name,
            optimized_prediction,
            dsp_example.expected_output_json,
            field_name,
            run.metric_config_snapshot_json,
        )
        baseline_metric = score_metric(
            metric_name,
            baseline_prediction,
            dsp_example.expected_output_json,
            field_name,
            run.metric_config_snapshot_json,
        )
        baseline_scores.append(baseline_metric["score"])
        optimized_scores.append(optimized_metric["score"])
        baseline_results.append(
            {
                "example_id": dsp_example.example_id,
                "split": dsp_example.split,
                "prediction": strip_internal_prediction_fields(baseline_prediction),
                "score": baseline_metric["score"],
                "error_type": baseline_metric["error_type"],
                "correct": baseline_metric["correct"],
                "rationale": baseline_metric.get("rationale"),
            }
        )
        optimized_results.append(
            {
                "example_id": dsp_example.example_id,
                "split": dsp_example.split,
                "prediction": strip_internal_prediction_fields(optimized_prediction),
                "score": optimized_metric["score"],
                "error_type": optimized_metric["error_type"],
                "correct": optimized_metric["correct"],
                "rationale": optimized_metric.get("rationale"),
            }
        )

    baseline_score = mean(baseline_scores) if baseline_scores else 0.0
    optimized_score = mean(optimized_scores) if optimized_scores else 0.0
    summary = {
        "baseline_score": baseline_score,
        "optimized_score": optimized_score,
        "delta": optimized_score - baseline_score,
        "optimizer_name": run.optimizer_name,
    }
    result_rows = [
        {
            "example_id": base["example_id"],
            "split": base["split"],
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
    failed_examples = [row for row in result_rows if row["optimized_score"] < 1.0]
    regression_examples = [row for row in result_rows if row["delta"] < 0]
    executive_summary = generate_report_summary(
        report_type="optimization",
        summary_payload=summary,
        warnings=list(run.dataset_split_snapshot_json.get("quality_summary_json", {}).get("warnings", [])),
        failures=regression_examples or failed_examples,
        model_name=run.model_config_snapshot_json.get("model"),
    )
    report = {
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
        },
        "score_breakdown": {
            "baseline_by_split": aggregate_scores(baseline_results, "split"),
            "optimized_by_split": aggregate_scores(optimized_results, "split"),
            "optimized_by_error_type": aggregate_scores(optimized_results, "error_type"),
        },
        "failed_examples": failed_examples,
        "regression_examples": regression_examples,
        "results": result_rows,
        "warnings": list(run.dataset_split_snapshot_json.get("quality_summary_json", {}).get("warnings", [])),
        "artifacts": [
            {"artifact_type": "report", "file_name": "report.json"},
            {"artifact_type": "predictions", "file_name": "predictions.json"},
            {"artifact_type": "optimized_prompt", "file_name": "optimized_prompt.json"},
            {"artifact_type": "prompt_diff", "file_name": "prompt_diff.json"},
            {"artifact_type": "compiled_program", "file_name": "compiled_program.json"},
            {"artifact_type": "fewshot_demos", "file_name": "fewshot_demos.json"},
        ],
    }
    return {
        "baseline_score": baseline_score,
        "optimized_score": optimized_score,
        "report": report,
        "baseline_results": baseline_results,
        "optimized_results": optimized_results,
        "optimized_prompt": optimized_prompt,
        "prompt_diff": prompt_diff,
        "compiled_program": dump_program_state(optimized_program),
        "fewshot_demos": extract_predictor_demos(optimized_program),
    }


def validate_optimizer_inputs(
    *,
    optimizer_name: str,
    split_snapshot: dict[str, Any],
    metric_config_snapshot_json: dict[str, Any],
) -> None:
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


def finalize_optimization_success(db: Session, run: OptimizationRun, result: dict[str, Any]) -> None:
    run.status = "succeeded"
    run.progress = 100
    run.baseline_score = result["baseline_score"]
    run.optimized_score = result["optimized_score"]
    run.finished_at = utcnow()
    run.artifact_dir = f"artifacts/optimization_runs/{run.id}"
    db.add(run)

    write_owner_artifact(db, "optimization_run", run.id, "report", "report.json", result["report"])
    write_owner_artifact(db, "optimization_run", run.id, "predictions", "predictions.json", result["optimized_results"])
    write_owner_artifact(db, "optimization_run", run.id, "optimized_prompt", "optimized_prompt.json", result["optimized_prompt"])
    write_owner_artifact(db, "optimization_run", run.id, "prompt_diff", "prompt_diff.json", result["prompt_diff"])
    write_owner_artifact(db, "optimization_run", run.id, "compiled_program", "compiled_program.json", result["compiled_program"])
    write_owner_artifact(db, "optimization_run", run.id, "fewshot_demos", "fewshot_demos.json", result["fewshot_demos"])
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
    run.status = "failed"
    run.error_message = error_message
    run.finished_at = utcnow()
    db.add(run)
    add_run_log(db, "optimization", run.id, "error", error_message)
    db.flush()


def build_optimized_prompt(prompt_snapshot_json: dict[str, Any], optimizer_name: str, optimized_program) -> dict[str, Any]:
    system_prompt = prompt_snapshot_json["system_prompt"]
    user_template = prompt_snapshot_json["user_template"]
    learned_instruction = getattr(getattr(optimized_program, "predict", None), "signature", None)
    learned_text = getattr(learned_instruction, "instructions", "")
    suffix = f"\n\nOptimizer note: refined by {optimizer_name}."
    if learned_text:
        suffix += f"\n\nLearned instructions:\n{learned_text}"
    return {
        **prompt_snapshot_json,
        "system_prompt": f"{system_prompt}{suffix}" if system_prompt else suffix.strip(),
        "user_template": user_template,
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
    if optimizer_name == "bootstrap_fewshot":
        optimizer = dspy.BootstrapFewShot(
            metric=metric,
            max_bootstrapped_demos=optimizer_config.get("max_bootstrapped_demos", 4),
            max_labeled_demos=optimizer_config.get("max_labeled_demos", 4),
            max_rounds=optimizer_config.get("max_rounds", 1),
        )
        if not bundle.trainset:
            raise bad_request("BootstrapFewShot requires train split examples")
        return optimizer.compile(program, trainset=bundle.trainset)

    if optimizer_name == "miprov2":
        if not bundle.trainset or not bundle.devset:
            raise bad_request("MIPROv2 requires both train and dev split examples")
        optimizer = dspy.MIPROv2(
            metric=metric,
            auto=optimizer_config.get("auto", "light"),
            num_threads=optimizer_config.get("num_threads"),
            max_bootstrapped_demos=optimizer_config.get("max_bootstrapped_demos", 4),
            max_labeled_demos=optimizer_config.get("max_labeled_demos", 4),
            seed=optimizer_config.get("seed", 9),
            verbose=optimizer_config.get("verbose", False),
        )
        compile_kwargs = {
            "trainset": bundle.trainset,
            "valset": bundle.devset,
            "minibatch": optimizer_config.get("minibatch", True),
            "minibatch_size": optimizer_config.get("minibatch_size", 35),
            "minibatch_full_eval_steps": optimizer_config.get("minibatch_full_eval_steps", 5),
        }
        if optimizer_config.get("num_trials") is not None:
            compile_kwargs["num_trials"] = optimizer_config["num_trials"]
        return optimizer.compile(program, **compile_kwargs)

    if optimizer_name == "gepa":
        if not bundle.trainset or not bundle.devset:
            raise bad_request("GEPA requires both train and dev split examples")
        optimizer = dspy.GEPA(
            metric=metric,
            auto=optimizer_config.get("auto", "light"),
            max_metric_calls=optimizer_config.get("max_metric_calls"),
            num_threads=optimizer_config.get("num_threads"),
            track_stats=optimizer_config.get("track_stats", True),
            log_dir=optimizer_config.get("log_dir"),
            seed=optimizer_config.get("seed", 0),
        )
        return optimizer.compile(program, trainset=bundle.trainset, valset=bundle.devset)

    raise bad_request(f"unsupported optimizer: {optimizer_name}")


def run_program_prediction(runtime, program, dsp_example, output_schema_json: dict[str, Any]) -> dict[str, Any]:
    if runtime.provider == "mock":
        return dict(dsp_example.expected_output_json)
    prediction = program(text=dsp_example.text)
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
    def metric(gold, pred, trace=None, pred_name=None, pred_trace=None):
        parsed_prediction = parse_prediction_output(output_schema_json, getattr(pred, "answer", ""))
        result = score_metric(metric_name, parsed_prediction, gold.expected_output_json, field_name, metric_config)
        if feedback:
            feedback_text = result.get("feedback") or (
                f"Input: {gold.text}\n"
                f"Expected: {gold.expected_output_json}\n"
                f"Actual: {strip_internal_prediction_fields(parsed_prediction)}\n"
                f"Error type: {result['error_type'] or 'none'}\n"
                "If wrong, adjust instructions to better match the expected structure and label."
            )
            return ScoreWithFeedback(score=float(result["score"]), feedback=feedback_text)
        return bool(result["correct"])

    return metric
