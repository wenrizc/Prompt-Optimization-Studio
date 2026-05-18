"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { JsonView } from "@/components/json-view";
import { Panel } from "@/components/panel";
import { StatusChip } from "@/components/status-chip";
import { WorkspacePicker } from "@/components/workspace-picker";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import {
  DEFAULT_LLM_MODEL,
  DEFAULT_LLM_PROVIDER,
  OptimizationRunRecord,
  RunLogRecord,
  asTextareaValue,
  formatScore,
  readJson,
  toErrorMessage,
} from "@/lib/studio";
import { useStudioWorkspace } from "@/lib/use-studio-workspace";

export default function OptimizationRunsPage() {
  const { t } = useI18n();
  const {
    projects,
    datasets,
    prompts,
    selectedProjectId,
    selectedDatasetId,
    selectedPromptId,
    setSelectedProjectId,
    setSelectedDatasetId,
    setSelectedPromptId,
  } = useStudioWorkspace();
  const [runs, setRuns] = useState<OptimizationRunRecord[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [selectedReport, setSelectedReport] = useState<unknown>(null);
  const [logs, setLogs] = useState<RunLogRecord[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const filteredRuns = useMemo(
    () => (selectedProjectId ? runs.filter((item) => item.project_id === selectedProjectId) : runs),
    [runs, selectedProjectId],
  );

  async function refreshRuns() {
    try {
      const result = await api.get<{ items: OptimizationRunRecord[] }>("/api/v1/optimization-runs");
      setRuns(result.items);
    } catch (refreshError) {
      setError(toErrorMessage(refreshError));
    }
  }

  async function loadRunDetail(runId: number) {
    try {
      const [report, logResponse] = await Promise.all([
        api.get(`/api/v1/optimization-runs/${runId}/report`),
        api.get<{ items: RunLogRecord[] }>(`/api/v1/run-logs?run_type=optimization&run_id=${runId}`),
      ]);
      setSelectedReport(report);
      setLogs(logResponse.items);
    } catch (detailError) {
      setError(toErrorMessage(detailError));
    }
  }

  useEffect(() => {
    void refreshRuns();
  }, []);

  useEffect(() => {
    if (selectedRunId) {
      void loadRunDetail(selectedRunId);
    }
  }, [selectedRunId]);

  async function queueRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProjectId || !selectedDatasetId || !selectedPromptId) {
      setError(t("optimization.selectError"));
      return;
    }
    const form = new FormData(event.currentTarget);
    setError("");
    setMessage("");
    try {
      const created = await api.post<OptimizationRunRecord>("/api/v1/optimization-runs", {
        project_id: selectedProjectId,
        dataset_id: selectedDatasetId,
        prompt_id: selectedPromptId,
        optimizer_name: form.get("optimizer_name"),
        metric_config_snapshot_json: readJson(
          String(form.get("metric_config_snapshot_json") ?? ""),
          { metric: "json_field_accuracy", field: "label" },
        ),
        model_config_snapshot_json: {
          provider: form.get("provider"),
          model: form.get("model"),
        },
        optimizer_config_snapshot_json: readJson(String(form.get("optimizer_config_snapshot_json") ?? ""), {}),
        random_seed: Number(form.get("random_seed")),
      });
      setMessage(t("optimization.queuedMessage", { id: created.id }));
      await refreshRuns();
      setSelectedRunId(created.id);
    } catch (queueError) {
      setError(toErrorMessage(queueError));
    }
  }

  async function runWorker() {
    setError("");
    try {
      const result = await api.post("/api/v1/worker/run-once", { worker_id: "frontend-worker", max_jobs: 5 });
      setMessage(t("optimization.workerProcessed", { count: (result as { processed_jobs: number }).processed_jobs }));
      await refreshRuns();
      if (selectedRunId) {
        await loadRunDetail(selectedRunId);
      }
    } catch (workerError) {
      setError(toErrorMessage(workerError));
    }
  }

  return (
    <AppShell>
      <Panel
        title={t("optimization.title")}
        description={t("optimization.description")}
      >
        <WorkspacePicker
          projects={projects}
          datasets={datasets}
          prompts={prompts}
          selectedProjectId={selectedProjectId}
          selectedDatasetId={selectedDatasetId}
          selectedPromptId={selectedPromptId}
          onProjectChange={setSelectedProjectId}
          onDatasetChange={setSelectedDatasetId}
          onPromptChange={setSelectedPromptId}
        />
      </Panel>

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <Panel title={t("optimization.queueTitle")} description={t("optimization.queueDescription")}>
          <form onSubmit={queueRun} className="grid gap-4">
            <div className="grid gap-4 md:grid-cols-4">
              <select name="optimizer_name" defaultValue="bootstrap_fewshot" className="rounded-2xl border border-stone-300 bg-white px-4 py-3">
                <option value="bootstrap_fewshot">bootstrap_fewshot</option>
                <option value="miprov2">miprov2</option>
                <option value="gepa">gepa</option>
              </select>
              <select name="provider" defaultValue={DEFAULT_LLM_PROVIDER} className="rounded-2xl border border-stone-300 bg-white px-4 py-3">
                <option value="openai">openai</option>
                <option value="mock">mock</option>
              </select>
              <input name="model" defaultValue={DEFAULT_LLM_MODEL} className="rounded-2xl border border-stone-300 bg-white px-4 py-3" />
              <input name="random_seed" defaultValue="42" className="rounded-2xl border border-stone-300 bg-white px-4 py-3" />
            </div>
            <textarea
              name="metric_config_snapshot_json"
              rows={8}
              defaultValue={asTextareaValue({ metric: "json_field_accuracy", field: "label" })}
              className="rounded-3xl border border-stone-300 bg-white px-4 py-3 font-mono text-sm"
            />
            <textarea
              name="optimizer_config_snapshot_json"
              rows={10}
              defaultValue={asTextareaValue({ max_labeled_demos: 4, max_bootstrapped_demos: 4 })}
              className="rounded-3xl border border-stone-300 bg-white px-4 py-3 font-mono text-sm"
            />
            <div className="flex flex-wrap gap-3">
              <button className="rounded-3xl bg-blue-700 px-5 py-3 text-sm font-medium text-white" type="submit">
                {t("optimization.queueButton")}
              </button>
              <button onClick={() => void runWorker()} className="rounded-3xl border border-stone-300 bg-white px-5 py-3 text-sm font-medium text-stone-800" type="button">
                {t("common.workerRunOnce")}
              </button>
            </div>
          </form>
          {message ? <p className="mt-4 text-sm text-emerald-700">{message}</p> : null}
          {error ? <p className="mt-4 text-sm text-rose-700">{error}</p> : null}
        </Panel>

        <Panel title={t("optimization.runQueueTitle")} description={t("optimization.runQueueDescription")}>
          <div className="grid gap-3">
            {filteredRuns.map((run) => (
              <button
                key={run.id}
                onClick={() => setSelectedRunId(run.id)}
                type="button"
                className={`rounded-3xl border px-4 py-4 text-left ${
                  selectedRunId === run.id
                    ? "border-blue-700 bg-blue-50"
                    : "border-stone-200 bg-white"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-stone-900">
                      {t("optimization.queueItemTitle", {
                        id: run.id,
                        optimizer: run.optimizer_name,
                      })}
                    </p>
                    <p className="mt-1 text-xs text-stone-500">
                      {t("optimization.baselineOptimized", {
                        baseline: formatScore(run.baseline_score),
                        optimized: formatScore(run.optimized_score),
                      })}
                    </p>
                  </div>
                  <StatusChip value={run.status} />
                </div>
              </button>
            ))}
          </div>
        </Panel>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title={t("optimization.reportTitle")} description={t("optimization.reportDescription")}>
          <JsonView value={selectedReport} emptyLabel={t("optimization.reportEmpty")} />
        </Panel>
        <Panel title={t("optimization.logsTitle")} description={t("optimization.logsDescription")}>
          <JsonView value={logs} emptyLabel={t("optimization.logsEmpty")} />
        </Panel>
      </div>
    </AppShell>
  );
}
