"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { JsonView } from "@/components/json-view";
import { Panel } from "@/components/panel";
import { StatusChip } from "@/components/status-chip";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import {
  Dataset,
  EvaluationRecord,
  OptimizationRunRecord,
  Project,
  PromptRecord,
  RunLogRecord,
  formatScore,
  toErrorMessage,
} from "@/lib/studio";

function MetricCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-[28px] border border-stone-900/10 bg-white p-5 shadow-sm">
      <p className="text-xs uppercase tracking-[0.2em] text-stone-500">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-stone-900">{value}</p>
      <p className="mt-2 text-sm text-stone-500">{hint}</p>
    </div>
  );
}

export default function HomePage() {
  const { t, tm, href } = useI18n();
  const [projects, setProjects] = useState<Project[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [prompts, setPrompts] = useState<PromptRecord[]>([]);
  const [evaluations, setEvaluations] = useState<EvaluationRecord[]>([]);
  const [runs, setRuns] = useState<OptimizationRunRecord[]>([]);
  const [logs, setLogs] = useState<RunLogRecord[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    void Promise.all([
      api.get<{ items: Project[] }>("/api/v1/projects").then((result) => setProjects(result.items)),
      api.get<{ items: Dataset[] }>("/api/v1/datasets").then((result) => setDatasets(result.items)),
      api.get<{ items: PromptRecord[] }>("/api/v1/prompts").then((result) => setPrompts(result.items)),
      api.get<{ items: EvaluationRecord[] }>("/api/v1/evaluations").then((result) => setEvaluations(result.items)),
      api.get<{ items: OptimizationRunRecord[] }>("/api/v1/optimization-runs").then((result) => setRuns(result.items)),
      api.get<{ items: RunLogRecord[] }>("/api/v1/run-logs").then((result) => setLogs(result.items.slice(0, 8))),
    ]).catch((loadError) => setError(toErrorMessage(loadError)));
  }, []);

  const activeProjects = projects.filter((item) => item.status === "active").length;
  const successfulEvaluations = evaluations.filter((item) => item.status === "succeeded");
  const successfulRuns = runs.filter((item) => item.status === "succeeded");
  const bestRun = useMemo(
    () =>
      [...successfulRuns]
        .filter((item) => item.baseline_score != null && item.optimized_score != null)
        .sort(
          (left, right) =>
            (right.optimized_score! - right.baseline_score!) - (left.optimized_score! - left.baseline_score!),
        )[0] ?? null,
    [successfulRuns],
  );
  const datasetSummary = useMemo(
    () =>
      datasets.slice(0, 5).map((dataset) => ({
        id: dataset.id,
        name: dataset.name,
        source_type: dataset.source_type,
        trust_level: String(dataset.quality_summary_json?.trust_level ?? "unknown"),
        total_examples: Number(dataset.quality_summary_json?.total_examples ?? 0),
      })),
    [datasets],
  );

  return (
    <AppShell>
      <Panel
        title={t("home.title")}
        description={t("home.description")}
      >
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label={t("home.metrics.activeProjects")}
            value={String(activeProjects)}
            hint={t("home.metrics.activeProjectsHint", { count: projects.length })}
          />
          <MetricCard
            label={t("home.metrics.datasets")}
            value={String(datasets.length)}
            hint={t("home.metrics.datasetsHint")}
          />
          <MetricCard
            label={t("home.metrics.evaluations")}
            value={String(evaluations.length)}
            hint={t("home.metrics.evaluationsHint", { count: successfulEvaluations.length })}
          />
          <MetricCard
            label={t("home.metrics.optimizationRuns")}
            value={String(runs.length)}
            hint={
              bestRun
                ? t("home.metrics.optimizationRunsHint", {
                    delta: formatScore(bestRun.optimized_score! - bestRun.baseline_score!),
                  })
                : t("home.metrics.noOptimizerDelta")
            }
          />
        </div>
      </Panel>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Panel title={t("home.quickActions.title")} description={t("home.quickActions.description")}>
          <div className="grid gap-4 md:grid-cols-2">
            {(tm<Array<{ href: string; title: string; description: string }>>("home.quickActions.items") ?? []).map((item) => (
              <Link
                key={item.href}
                href={href(item.href)}
                className="rounded-[28px] border border-stone-900/10 bg-white p-5 transition hover:border-teal-700 hover:shadow-md"
              >
                <p className="text-base font-semibold text-stone-900">{item.title}</p>
                <p className="mt-2 text-sm text-stone-500">{item.description}</p>
              </Link>
            ))}
          </div>
        </Panel>

        <Panel title={t("home.bestRun.title")} description={t("home.bestRun.description")}>
          {bestRun ? (
            <div className="rounded-[28px] border border-emerald-200 bg-emerald-50 p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-stone-900">
                    {t("home.bestRun.runTitle", {
                      id: bestRun.id,
                      optimizer: bestRun.optimizer_name,
                    })}
                  </p>
                  <p className="mt-1 text-sm text-stone-500">
                    {t("home.bestRun.baselineToOptimized", {
                      baseline: formatScore(bestRun.baseline_score),
                      optimized: formatScore(bestRun.optimized_score),
                    })}
                  </p>
                </div>
                <StatusChip value={bestRun.status} />
              </div>
              <p className="mt-4 text-3xl font-semibold text-emerald-800">
                Δ {formatScore(bestRun.optimized_score! - bestRun.baseline_score!)}
              </p>
              <Link href={href("/reports")} className="mt-4 inline-flex rounded-full bg-emerald-700 px-4 py-2 text-sm font-medium text-white">
                {t("home.bestRun.openReport")}
              </Link>
            </div>
          ) : (
            <JsonView value={null} emptyLabel={t("home.bestRun.empty")} />
          )}
        </Panel>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <Panel title={t("home.trustSnapshot.title")} description={t("home.trustSnapshot.description")}>
          <JsonView value={datasetSummary} emptyLabel={t("home.trustSnapshot.empty")} />
        </Panel>
        <Panel title={t("home.recentLogs.title")} description={t("home.recentLogs.description")}>
          <JsonView value={logs} emptyLabel={t("home.recentLogs.empty")} />
        </Panel>
      </div>

      {error ? (
        <Panel title={t("common.loadError")}>
          <p className="text-sm text-rose-700">{error}</p>
        </Panel>
      ) : null}
    </AppShell>
  );
}
