"use client";

import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { DataTable } from "@/components/data-table";
import { Panel } from "@/components/panel";
import { StatusChip } from "@/components/status-chip";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { OptimizationRunRecord, formatScore, toErrorMessage } from "@/lib/studio";

export default function RunComparisonPage() {
  const { t } = useI18n();
  const [runs, setRuns] = useState<OptimizationRunRecord[]>([]);
  const [selectedRunIds, setSelectedRunIds] = useState<number[]>([]);
  const [comparisonRows, setComparisonRows] = useState<Record<string, unknown>[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<{ items: OptimizationRunRecord[] }>("/api/v1/optimization-runs")
      .then((result) => setRuns(result.items))
      .catch((loadError) => setError(toErrorMessage(loadError)));
  }, []);

  const selectableRuns = useMemo(
    () => runs.filter((item) => item.status === "succeeded"),
    [runs],
  );

  async function compareSelectedRuns() {
    if (selectedRunIds.length === 0) {
      return;
    }
    try {
      const result = await api.get<{ items: Record<string, unknown>[] }>(
        `/api/v1/optimization-runs/compare/runs?run_ids=${selectedRunIds.join(",")}`,
      );
      setComparisonRows(result.items);
    } catch (compareError) {
      setError(toErrorMessage(compareError));
    }
  }

  function toggleRun(runId: number) {
    setSelectedRunIds((current) =>
      current.includes(runId) ? current.filter((item) => item !== runId) : [...current, runId],
    );
  }

  return (
    <AppShell>
      <Panel title={t("runComparison.title")} description={t("runComparison.description")}>
        <div className="mb-4 flex flex-wrap gap-3">
          <button onClick={() => void compareSelectedRuns()} className="rounded-3xl bg-indigo-700 px-5 py-3 text-sm font-medium text-white" type="button">
            {t("runComparison.compareButton")}
          </button>
          <p className="text-sm text-stone-500">
            {t("runComparison.selectedRuns", { count: selectedRunIds.length })}
          </p>
        </div>
        <div className="grid gap-3">
          {selectableRuns.map((run) => {
            const selected = selectedRunIds.includes(run.id);
            return (
              <button
                key={run.id}
                onClick={() => toggleRun(run.id)}
                type="button"
                className={`rounded-3xl border px-4 py-4 text-left ${
                  selected ? "border-indigo-700 bg-indigo-50" : "border-stone-200 bg-white"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-stone-900">
                      {t("runComparison.runItemTitle", {
                        id: run.id,
                        optimizer: run.optimizer_name,
                      })}
                    </p>
                    <p className="mt-1 text-xs text-stone-500">
                      {t("runComparison.baselineOptimized", {
                        baseline: formatScore(run.baseline_score),
                        optimized: formatScore(run.optimized_score),
                      })}
                    </p>
                  </div>
                  <StatusChip value={run.status} />
                </div>
              </button>
            );
          })}
        </div>
        {error ? <p className="mt-4 text-sm text-rose-700">{error}</p> : null}
      </Panel>

      <Panel title={t("runComparison.tableTitle")} description={t("runComparison.tableDescription")}>
        <DataTable rows={comparisonRows} />
      </Panel>
    </AppShell>
  );
}
