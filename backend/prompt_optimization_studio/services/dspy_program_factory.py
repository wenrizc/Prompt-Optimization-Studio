import json
from dataclasses import dataclass
from typing import Any

import dspy

from prompt_optimization_studio.models.dataset import DatasetExample


@dataclass
class DSPyDatasetBundle:
    trainset: list[dspy.Example]
    devset: list[dspy.Example]
    testset: list[dspy.Example]
    all_examples: list[dspy.Example]


class PromptOptimizationProgram(dspy.Module):
    def __init__(self, instructions: str):
        super().__init__()
        signature = dspy.Signature("text -> answer", instructions=instructions)
        self.predict = dspy.Predict(signature)

    def forward(self, text: str):
        return self.predict(text=text)


def build_program(prompt_snapshot_json: dict[str, Any]) -> PromptOptimizationProgram:
    instructions = build_instructions(prompt_snapshot_json)
    return PromptOptimizationProgram(instructions=instructions)


def build_instructions(prompt_snapshot_json: dict[str, Any]) -> str:
    system_prompt = (prompt_snapshot_json.get("system_prompt") or "").strip()
    user_template = (prompt_snapshot_json.get("user_template") or "{text}").strip()
    output_schema_json = prompt_snapshot_json.get("output_schema_json") or {}
    schema_text = json.dumps(output_schema_json, ensure_ascii=False, indent=2)
    parts = [
        "You are executing a prompt optimization task.",
        "Follow the instruction and produce the final answer only.",
        f"System prompt:\n{system_prompt}" if system_prompt else "System prompt: <empty>",
        f"User template:\n{user_template}",
        f"Output schema:\n{schema_text}",
        "Return the answer so it can be parsed against the schema.",
    ]
    return "\n\n".join(parts)


def build_dataset_bundle(
    examples: list[DatasetExample],
    prompt_snapshot_json: dict[str, Any],
) -> DSPyDatasetBundle:
    converted = [to_dspy_example(example, prompt_snapshot_json) for example in examples]
    trainset = [example for example in converted if example.split == "train"]
    devset = [example for example in converted if example.split == "dev"]
    testset = [example for example in converted if example.split == "test"]
    if not testset:
        fallback = devset or trainset
        testset = list(fallback)
    return DSPyDatasetBundle(trainset=trainset, devset=devset, testset=testset, all_examples=converted)


def to_dspy_example(example: DatasetExample, prompt_snapshot_json: dict[str, Any]) -> dspy.Example:
    rendered_text = render_user_text(prompt_snapshot_json.get("user_template") or "{text}", example.input_json)
    answer = stringify_expected_output(prompt_snapshot_json.get("output_schema_json") or {}, example.expected_output_json)
    return (
        dspy.Example(
            text=rendered_text,
            answer=answer,
            expected_output_json=example.expected_output_json,
            example_id=example.id,
            split=example.split,
            quality_status=example.quality_status,
        ).with_inputs("text")
    )


def render_user_text(user_template: str, input_json: dict[str, Any]) -> str:
    rendered = user_template
    for key, value in input_json.items():
        rendered = rendered.replace(f"{{{key}}}", str(value))
    return rendered


def stringify_expected_output(output_schema_json: dict[str, Any], expected_output_json: dict[str, Any]) -> str:
    schema_type = output_schema_json.get("type")
    if schema_type == "string":
        if isinstance(expected_output_json, dict) and "answer" in expected_output_json:
            return str(expected_output_json["answer"])
    return json.dumps(expected_output_json, ensure_ascii=False, sort_keys=True)


def parse_prediction_output(output_schema_json: dict[str, Any], answer: str) -> dict[str, Any]:
    schema_type = output_schema_json.get("type")
    if schema_type == "string":
        return {"answer": answer.strip()}

    try:
        parsed = json.loads(answer)
        if isinstance(parsed, dict):
            return parsed
        return {
            "answer": parsed,
            "__meta__": {"error_type": "schema_error", "raw_answer": answer},
        }
    except Exception:
        return {
            "answer": answer.strip(),
            "__meta__": {"error_type": "parse_error", "raw_answer": answer},
        }


def strip_internal_prediction_fields(prediction: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in prediction.items() if not key.startswith("__")}


def extract_predictor_demos(program: dspy.Module) -> list[dict[str, Any]]:
    demos: list[dict[str, Any]] = []
    for name, predictor in program.named_predictors():
        for demo in getattr(predictor, "demos", []):
            demos.append(
                {
                    "predictor": name,
                    "text": getattr(demo, "text", None),
                    "answer": getattr(demo, "answer", None),
                }
            )
    return demos


def dump_program_state(program: dspy.Module) -> dict[str, Any]:
    return {
        "module_type": type(program).__name__,
        "state": program.dump_state(),
        "demos": extract_predictor_demos(program),
    }
