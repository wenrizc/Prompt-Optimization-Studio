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
  EvaluationRecord,
  OptimizationRunRecord,
  RunLogRecord,
  asTextareaValue,
  formatScore,
  readJson,
  toErrorMessage,
} from "@/lib/studio";
import { useStudioWorkspace } from "@/lib/use-studio-workspace";

type RunMode = "evaluation" | "optimization";

export default function RunsPage() {
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
  const [mode, setMode] = useState<RunMode>("evaluation");
  const [evaluations, setEvaluations] = useState<EvaluationRecord[]>([]);
  const [runs, setRuns] = useState<OptimizationRunRecord[]>([]);
  const [selectedEvaluationId, setSelectedEvaluationId] = useState<number | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [selectedReport, setSelectedReport] = useState<unknown>(null);
  const [logs, setLogs] = useState<RunLogRecord[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const isEvaluationMode = mode === "evaluation";

  async function refreshAllRuns() {
    try {
      const [evaluationResult, runResult] = await Promise.all([
        api.get<{ items: EvaluationRecord[] }>("/api/v1/evaluations"),
        api.get<{ items: OptimizationRunRecord[] }>("/api/v1/optimization-runs"),
      ]);
      setEvaluations(evaluationResult.items);
      setRuns(runResult.items);
    } catch (refreshError) {
      setError(toErrorMessage(refreshError));
    }
  }

  useEffect(() => {
    void refreshAllRuns();
  }, []);

  const filteredEvaluations = useMemo(
    () => (selectedProjectId ? evaluations.filter((item) => item.project_id === selectedProjectId) : evaluations),
    [evaluations, selectedProjectId],
  );
  const filteredRuns = useMemo(
    () => (selectedProjectId ? runs.filter((item) => item.project_id === selectedProjectId) : runs),
    [runs, selectedProjectId],
  );
  const selectedEvaluation = useMemo(
    () => evaluations.find((item) => item.id === selectedEvaluationId) ?? null,
    [evaluations, selectedEvaluationId],
  );
  const selectedRun = useMemo(
    () => runs.find((item) => item.id === selectedRunId) ?? null,
    [runs, selectedRunId],
  );

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

  async function loadOptimizationDetail(runId: number) {
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

  async function queueEvaluation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProjectId || !selectedDatasetId || !selectedPromptId) {
      setError(t("evaluations.selectError"));
      return;
    }
    setError("");
    setMessage("");
    try {
      const created = await api.post<EvaluationRecord>("/api/v1/evaluations", {
        project_id: selectedProjectId,
        dataset_id: selectedDatasetId,
        prompt_id: selectedPromptId,
      });
      setMessage(t("evaluations.queuedMessage", { id: created.id }));
      setSelectedEvaluationId(created.id);
      setSelectedRunId(null);
      await refreshAllRuns();
    } catch (queueError) {
      setError(toErrorMessage(queueError));
    }
  }

  async function queueOptimization(event: FormEvent<HTMLFormElement>) {
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
        optimizer_config_snapshot_json: readJson(String(form.get("optimizer_config_snapshot_json") ?? ""), {}),
      });
      setMessage(t("optimization.queuedMessage", { id: created.id }));
      setSelectedRunId(created.id);
      setSelectedEvaluationId(null);
      await refreshAllRuns();
    } catch (queueError) {
      setError(toErrorMessage(queueError));
    }
  }

  async function runWorker() {
    setError("");
    try {
      const result = await api.post("/api/v1/worker/run-once", {
        worker_id: "frontend-worker",
        max_jobs: 5,
      });
      const processedCount = (result as { processed_jobs: number }).processed_jobs;
      setMessage(
        mode === "evaluation"
          ? t("evaluations.workerProcessed", { count: processedCount })
          : t("optimization.workerProcessed", { count: processedCount }),
      );
      await refreshAllRuns();
      if (mode === "evaluation" && selectedEvaluationId) {
        await loadEvaluationDetail(selectedEvaluationId);
      }
      if (mode === "optimization" && selectedRunId) {
        await loadOptimizationDetail(selectedRunId);
      }
    } catch (workerError) {
      setError(toErrorMessage(workerError));
    }
  }

  return (
    <AppShell>
      <Panel title={t("runs.hub.title")} description={t("runs.hub.description")}>
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

      <div className="grid gap-6 xl:grid-cols-[1.06fr_0.94fr]">
        <Panel
          title={isEvaluationMode ? t("evaluations.title") : t("optimization.title")}
          description={isEvaluationMode ? t("evaluations.description") : t("optimization.description")}
        >
          <div className="mb-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => setMode("evaluation")}
              className={`rounded-3xl px-5 py-3 text-sm font-medium ${
                mode === "evaluation" ? "bg-stone-900 text-white" : "border border-stone-300 bg-white text-stone-800"
              }`}
            >
              {t("runs.hub.evaluationTab")}
            </button>
            <button
              type="button"
              onClick={() => setMode("optimization")}
              className={`rounded-3xl px-5 py-3 text-sm font-medium ${
                mode === "optimization" ? "bg-stone-900 text-white" : "border border-stone-300 bg-white text-stone-800"
              }`}
            >
              {t("runs.hub.optimizationTab")}
            </button>
          </div>

          <div className="mb-4 rounded-[24px] border border-stone-900/10 bg-stone-50 px-4 py-4">
            <p className="text-xs uppercase tracking-[0.18em] text-stone-500">
              {t("runs.hub.launchTitle")}
            </p>
            <p className="mt-2 text-sm text-stone-700">
              {isEvaluationMode ? t("evaluations.queueDescription") : t("optimization.queueDescription")}
            </p>
          </div>

          {isEvaluationMode ? (
            <form onSubmit={queueEvaluation} className="grid gap-4">
              <div className="flex flex-wrap gap-3">
                <button className="rounded-3xl bg-teal-700 px-5 py-3 text-sm font-medium text-white" type="submit">
                  {t("evaluations.queueButton")}
                </button>
                <button onClick={() => void runWorker()} className="rounded-3xl border border-stone-300 bg-white px-5 py-3 text-sm font-medium text-stone-800" type="button">
                  {t("common.workerRunOnce")}
                </button>
              </div>
            </form>
          ) : (
            <form onSubmit={queueOptimization} className="grid gap-4">
              <div className="grid gap-4 md:grid-cols-1">
                <select name="optimizer_name" defaultValue="bootstrap_fewshot" className="rounded-2xl border border-stone-300 bg-white px-4 py-3">
                  <option value="bootstrap_fewshot">bootstrap_fewshot</option>
                  <option value="miprov2">miprov2</option>
                  <option value="gepa">gepa</option>
                </select>
              </div>
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
          )}

          {message ? <p className="mt-4 text-sm text-emerald-700">{message}</p> : null}
          {error ? <p className="mt-4 text-sm text-rose-700">{error}</p> : null}
        </Panel>

        <Panel
          title={isEvaluationMode ? t("evaluations.queueListTitle") : t("optimization.runQueueTitle")}
          description={isEvaluationMode ? t("evaluations.queueListDescription") : t("optimization.runQueueDescription")}
        >
          <div className="grid gap-3">
            {isEvaluationMode
              ? filteredEvaluations.map((evaluation) => (
                  <button
                    key={evaluation.id}
                    onClick={() => {
                      setSelectedEvaluationId(evaluation.id);
                      setSelectedRunId(null);
                      void loadEvaluationDetail(evaluation.id);
                    }}
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
                ))
              : filteredRuns.map((run) => (
                  <button
                    key={run.id}
                    onClick={() => {
                      setSelectedRunId(run.id);
                      setSelectedEvaluationId(null);
                      void loadOptimizationDetail(run.id);
                    }}
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

      <Panel
        title={t("runs.hub.advancedTitle")}
        description={isEvaluationMode ? t("evaluations.reportDescription") : t("optimization.reportDescription")}
      >
        <details className="rounded-[28px] border border-stone-900/10 bg-white p-5">
          <summary className="cursor-pointer list-none text-sm font-semibold text-stone-900">
            {t("runs.hub.advancedToggle")}
          </summary>
          <div className="mt-5 grid gap-6 xl:grid-cols-2">
            <div>
              <h3 className="mb-2 text-sm font-semibold text-stone-900">{t("runs.hub.selectedRunTitle")}</h3>
              <JsonView value={isEvaluationMode ? selectedEvaluation : selectedRun} emptyLabel={t("runs.hub.selectedRunEmpty")} />
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold text-stone-900">
                {isEvaluationMode ? t("evaluations.reportTitle") : t("optimization.reportTitle")}
              </h3>
              <JsonView
                value={selectedReport}
                emptyLabel={isEvaluationMode ? t("evaluations.reportEmpty") : t("optimization.reportEmpty")}
              />
            </div>
            <div className="xl:col-span-2">
              <h3 className="mb-2 text-sm font-semibold text-stone-900">
                {isEvaluationMode ? t("evaluations.logsTitle") : t("optimization.logsTitle")}
              </h3>
              <JsonView
                value={logs}
                emptyLabel={isEvaluationMode ? t("evaluations.logsEmpty") : t("optimization.logsEmpty")}
              />
            </div>
          </div>
        </details>
      </Panel>
    </AppShell>
  );
}
