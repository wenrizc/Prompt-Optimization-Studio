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
  EvaluationRecord,
  RunLogRecord,
  asTextareaValue,
  formatScore,
  readJson,
  toErrorMessage,
} from "@/lib/studio";
import { useStudioWorkspace } from "@/lib/use-studio-workspace";

export default function EvaluationsPage() {
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
  const [evaluations, setEvaluations] = useState<EvaluationRecord[]>([]);
  const [selectedEvaluationId, setSelectedEvaluationId] = useState<number | null>(null);
  const [selectedReport, setSelectedReport] = useState<unknown>(null);
  const [logs, setLogs] = useState<RunLogRecord[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const filteredEvaluations = useMemo(
    () => (selectedProjectId ? evaluations.filter((item) => item.project_id === selectedProjectId) : evaluations),
    [evaluations, selectedProjectId],
  );

  async function refreshEvaluations() {
    try {
      const result = await api.get<{ items: EvaluationRecord[] }>("/api/v1/evaluations");
      setEvaluations(result.items);
    } catch (refreshError) {
      setError(toErrorMessage(refreshError));
    }
  }

  async function loadEvaluationDetail(evaluationId: number) {
    try {
      const [report, logResponse] = await Promise.all([
        api.get(`/api/v1/evaluations/${evaluationId}/report`),
        api.get<{ items: RunLogRecord[] }>(`/api/v1/run-logs?run_type=evaluation&run_id=${evaluationId}`),
      ]);
      setSelectedReport(report);
      setLogs(logResponse.items);
    } catch (detailError) {
      setError(toErrorMessage(detailError));
    }
  }

  useEffect(() => {
    void refreshEvaluations();
  }, []);

  useEffect(() => {
    if (selectedEvaluationId) {
      void loadEvaluationDetail(selectedEvaluationId);
    }
  }, [selectedEvaluationId]);

  async function queueEvaluation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProjectId || !selectedDatasetId || !selectedPromptId) {
      setError(t("evaluations.selectError"));
      return;
    }
    const form = new FormData(event.currentTarget);
    setError("");
    setMessage("");
    try {
      const created = await api.post<EvaluationRecord>("/api/v1/evaluations", {
        project_id: selectedProjectId,
        dataset_id: selectedDatasetId,
        prompt_id: selectedPromptId,
        metric_config_json: readJson(String(form.get("metric_config_json") ?? ""), { metric: "json_field_accuracy", field: "label" }),
        model_config_json: {
          provider: form.get("provider"),
          model: form.get("model"),
        },
        random_seed: Number(form.get("random_seed")),
      });
      setMessage(t("evaluations.queuedMessage", { id: created.id }));
      await refreshEvaluations();
      setSelectedEvaluationId(created.id);
    } catch (queueError) {
      setError(toErrorMessage(queueError));
    }
  }

  async function runWorker() {
    setError("");
    try {
      const result = await api.post("/api/v1/worker/run-once", { worker_id: "frontend-worker", max_jobs: 5 });
      setMessage(t("evaluations.workerProcessed", { count: (result as { processed_jobs: number }).processed_jobs }));
      await refreshEvaluations();
      if (selectedEvaluationId) {
        await loadEvaluationDetail(selectedEvaluationId);
      }
    } catch (workerError) {
      setError(toErrorMessage(workerError));
    }
  }

  return (
    <AppShell>
      <Panel
        title={t("evaluations.title")}
        description={t("evaluations.description")}
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
        <Panel title={t("evaluations.queueTitle")} description={t("evaluations.queueDescription")}>
          <form onSubmit={queueEvaluation} className="grid gap-4">
            <div className="grid gap-4 md:grid-cols-3">
              <select name="provider" defaultValue={DEFAULT_LLM_PROVIDER} className="rounded-2xl border border-stone-300 bg-white px-4 py-3">
                <option value="openai">openai</option>
                <option value="mock">mock</option>
              </select>
              <input name="model" defaultValue={DEFAULT_LLM_MODEL} className="rounded-2xl border border-stone-300 bg-white px-4 py-3" />
              <input name="random_seed" defaultValue="42" className="rounded-2xl border border-stone-300 bg-white px-4 py-3" />
            </div>
            <textarea
              name="metric_config_json"
              rows={8}
              defaultValue={asTextareaValue({ metric: "json_field_accuracy", field: "label" })}
              className="rounded-3xl border border-stone-300 bg-white px-4 py-3 font-mono text-sm"
            />
            <div className="flex flex-wrap gap-3">
              <button className="rounded-3xl bg-teal-700 px-5 py-3 text-sm font-medium text-white" type="submit">
                {t("evaluations.queueButton")}
              </button>
              <button onClick={() => void runWorker()} className="rounded-3xl border border-stone-300 bg-white px-5 py-3 text-sm font-medium text-stone-800" type="button">
                {t("common.workerRunOnce")}
              </button>
            </div>
          </form>
          {message ? <p className="mt-4 text-sm text-emerald-700">{message}</p> : null}
          {error ? <p className="mt-4 text-sm text-rose-700">{error}</p> : null}
        </Panel>

        <Panel title={t("evaluations.queueListTitle")} description={t("evaluations.queueListDescription")}>
          <div className="grid gap-3">
            {filteredEvaluations.map((evaluation) => (
              <button
                key={evaluation.id}
                onClick={() => setSelectedEvaluationId(evaluation.id)}
                type="button"
                className={`rounded-3xl border px-4 py-4 text-left ${
                  selectedEvaluationId === evaluation.id
                    ? "border-teal-700 bg-teal-50"
                    : "border-stone-200 bg-white"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-stone-900">
                      {t("evaluations.queueItemTitle", {
                        id: evaluation.id,
                        datasetId: evaluation.dataset_id,
                        promptId: evaluation.prompt_id,
                      })}
                    </p>
                    <p className="mt-1 text-xs text-stone-500">
                      {t("evaluations.scoreProgress", {
                        score: formatScore(evaluation.score),
                        progress: evaluation.progress,
                      })}
                    </p>
                  </div>
                  <StatusChip value={evaluation.status} />
                </div>
              </button>
            ))}
          </div>
        </Panel>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title={t("evaluations.reportTitle")} description={t("evaluations.reportDescription")}>
          <JsonView value={selectedReport} emptyLabel={t("evaluations.reportEmpty")} />
        </Panel>
        <Panel title={t("evaluations.logsTitle")} description={t("evaluations.logsDescription")}>
          <JsonView value={logs} emptyLabel={t("evaluations.logsEmpty")} />
        </Panel>
      </div>
    </AppShell>
  );
}
