"use client";

export type Project = {
  id: number;
  name: string;
  description: string | null;
  task_kind: string;
  task_key: string;
  task_display_name: string;
  task_description: string | null;
  input_schema_json: Record<string, unknown>;
  output_schema_json: Record<string, unknown>;
  default_metric_config_json: Record<string, unknown>;
  task_definition_json: Record<string, unknown>;
  report_profile_json: Record<string, unknown>;
  status: string;
};

export type Dataset = {
  id: number;
  project_id: number;
  name: string;
  source_type: string;
  schema_json: Record<string, unknown>;
  command: string | null;
  generation_model: string | null;
  parent_dataset_id: number | null;
  quality_summary_json: Record<string, unknown>;
  status: string;
};

export type PromptRecord = {
  id: number;
  project_id: number;
  name: string;
  system_prompt: string;
  user_template: string;
  output_schema_json: Record<string, unknown>;
  version: number;
  status: string;
};

export type EvaluationRecord = {
  id: number;
  project_id: number;
  dataset_id: number;
  prompt_id: number;
  status: string;
  progress: number;
  score: number | null;
  metric_config_json: Record<string, unknown>;
  model_config_json: Record<string, unknown>;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type OptimizationRunRecord = {
  id: number;
  project_id: number;
  dataset_id: number;
  prompt_id: number;
  optimizer_name: string;
  status: string;
  progress: number;
  baseline_score: number | null;
  optimized_score: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type DatasetExample = {
  id: number;
  dataset_id: number;
  split: string;
  input_json: Record<string, unknown>;
  expected_output_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  quality_status: string;
  content_hash: string;
};

export type JobRecord = {
  id: number;
  job_type: string;
  target_type: string;
  target_id: number;
  status: string;
  progress: number;
  error_message: string | null;
};

export type RunLogRecord = {
  id: number;
  run_type: string;
  run_id: number;
  level: string;
  message: string;
  data_json: Record<string, unknown> | null;
  created_at: string;
};

export const DEFAULT_LLM_PROVIDER =
  process.env.NEXT_PUBLIC_DEFAULT_LLM_PROVIDER ?? "openai";

export const DEFAULT_LLM_MODEL =
  process.env.NEXT_PUBLIC_DEFAULT_LLM_MODEL ?? "deepseek-v4-pro";

export const DEFAULT_GENERATION_MODEL =
  process.env.NEXT_PUBLIC_DEFAULT_GENERATION_MODEL ?? DEFAULT_LLM_MODEL;

export function toErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

export function readJson(text: string, fallback: Record<string, unknown> = {}): Record<string, unknown> {
  try {
    const parsed = JSON.parse(text);
    return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : fallback;
  } catch {
    return fallback;
  }
}

export function formatScore(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "—";
  }
  return value.toFixed(3);
}

export function asTextareaValue(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}
