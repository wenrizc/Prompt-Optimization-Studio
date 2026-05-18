"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { JsonView } from "@/components/json-view";
import { Panel } from "@/components/panel";
import { WorkspacePicker } from "@/components/workspace-picker";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { DatasetExample, toErrorMessage } from "@/lib/studio";
import { useStudioWorkspace } from "@/lib/use-studio-workspace";

export default function DatasetEditorPage() {
  const { t } = useI18n();
  const {
    projects,
    datasets,
    prompts,
    selectedProjectId,
    selectedDatasetId,
    setSelectedProjectId,
    setSelectedDatasetId,
  } = useStudioWorkspace();
  const [examples, setExamples] = useState<DatasetExample[]>([]);
  const [qualityReport, setQualityReport] = useState<unknown>(null);
  const [selectedExampleId, setSelectedExampleId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const selectedDataset = useMemo(
    () => datasets.find((item) => item.id === selectedDatasetId) ?? null,
    [datasets, selectedDatasetId],
  );
  const selectedExample = useMemo(
    () => examples.find((item) => item.id === selectedExampleId) ?? null,
    [examples, selectedExampleId],
  );

  async function loadDatasetState(datasetId: number) {
    setLoading(true);
    setError("");
    try {
      const [exampleResponse, qualityResponse] = await Promise.all([
        api.get<{ items: DatasetExample[] }>(`/api/v1/datasets/${datasetId}/examples?page_size=100`),
        api.get(`/api/v1/datasets/${datasetId}/quality-report`),
      ]);
      setExamples(exampleResponse.items);
      setQualityReport(qualityResponse);
    } catch (loadError) {
      setError(toErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (selectedDatasetId) {
      void loadDatasetState(selectedDatasetId);
    }
  }, [selectedDatasetId]);

  async function reviewExamples(status: string) {
    if (!selectedDatasetId || examples.length === 0) {
      return;
    }
    try {
      await api.post(`/api/v1/datasets/${selectedDatasetId}/examples/review`, {
        example_ids: examples.slice(0, 20).map((item) => item.id),
        quality_status: status,
      });
      await loadDatasetState(selectedDatasetId);
    } catch (reviewError) {
      setError(toErrorMessage(reviewError));
    }
  }

  async function splitDataset() {
    if (!selectedDatasetId) {
      return;
    }
    try {
      await api.post(`/api/v1/datasets/${selectedDatasetId}/split`, {
        train_ratio: 0.6,
        dev_ratio: 0.2,
        test_ratio: 0.2,
        include_needs_review: false,
      });
      await loadDatasetState(selectedDatasetId);
    } catch (splitError) {
      setError(toErrorMessage(splitError));
    }
  }

  async function updateExample(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedDatasetId || !selectedExampleId) {
      return;
    }
    const form = new FormData(event.currentTarget);
    try {
      await api.patch(`/api/v1/datasets/${selectedDatasetId}/examples/${selectedExampleId}`, {
        split: form.get("split"),
        quality_status: form.get("quality_status"),
        input_json: { text: form.get("text") },
        expected_output_json: JSON.parse(String(form.get("expected_output_json") ?? "{}")),
      });
      await loadDatasetState(selectedDatasetId);
    } catch (updateError) {
      setError(toErrorMessage(updateError));
    }
  }

  const previewRows = examples.slice(0, 12).map((item) => ({
    id: item.id,
    split: item.split,
    quality_status: item.quality_status,
    text: item.input_json.text,
    expected_output_json: item.expected_output_json,
  }));

  return (
    <AppShell>
      <Panel
        title={t("datasets.editor.title")}
        description={t("datasets.editor.description")}
      >
        <WorkspacePicker
          projects={projects}
          datasets={datasets}
          prompts={prompts}
          selectedProjectId={selectedProjectId}
          selectedDatasetId={selectedDatasetId}
          onProjectChange={setSelectedProjectId}
          onDatasetChange={setSelectedDatasetId}
        />
      </Panel>

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <Panel title={t("datasets.editor.previewTitle")} description={t("datasets.editor.previewDescription")}>
          <div className="mb-4 flex flex-wrap gap-3">
            <button onClick={() => selectedDatasetId && void loadDatasetState(selectedDatasetId)} className="rounded-3xl bg-sky-700 px-5 py-3 text-sm font-medium text-white" type="button">
              {t("datasets.editor.refreshExamples")}
            </button>
            <button onClick={() => void reviewExamples("accepted")} className="rounded-3xl border border-stone-300 bg-white px-5 py-3 text-sm font-medium text-stone-800" type="button">
              {t("datasets.editor.acceptFirst20")}
            </button>
            <button onClick={() => void reviewExamples("needs_review")} className="rounded-3xl border border-stone-300 bg-white px-5 py-3 text-sm font-medium text-stone-800" type="button">
              {t("datasets.editor.markFirst20NeedsReview")}
            </button>
            <button onClick={() => void splitDataset()} className="rounded-3xl border border-stone-300 bg-white px-5 py-3 text-sm font-medium text-stone-800" type="button">
              {t("datasets.editor.resplit")}
            </button>
          </div>
          {loading ? <p className="mb-4 text-sm text-stone-500">{t("common.loadingDatasetState")}</p> : null}
          {error ? <p className="mb-4 text-sm text-rose-700">{error}</p> : null}
          <div className="grid gap-3">
            {previewRows.map((row) => (
              <button
                key={String(row.id)}
                onClick={() => setSelectedExampleId(Number(row.id))}
                type="button"
                className={`rounded-3xl border px-4 py-4 text-left ${
                  selectedExampleId === row.id ? "border-sky-700 bg-sky-50" : "border-stone-200 bg-white"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-stone-900">#{row.id}</p>
                    <p className="mt-1 text-xs text-stone-500">{String(row.text)}</p>
                  </div>
                  <div className="text-right text-xs text-stone-500">
                    <p>{String(row.split)}</p>
                    <p>{String(row.quality_status)}</p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </Panel>

        <Panel title={t("datasets.editor.diagnosticsTitle")} description={t("datasets.editor.diagnosticsDescription")}>
          <div className="space-y-4">
            <div>
              <h3 className="mb-2 text-sm font-semibold text-stone-900">{t("datasets.editor.selectedExampleEditor")}</h3>
              {selectedExample ? (
                <form onSubmit={updateExample} className="grid gap-3 rounded-3xl border border-stone-200 bg-white p-4">
                  <input
                    name="text"
                    defaultValue={String(selectedExample.input_json.text ?? "")}
                    className="rounded-2xl border border-stone-300 bg-white px-4 py-3"
                  />
                  <div className="grid gap-3 md:grid-cols-2">
                    <select name="split" defaultValue={selectedExample.split} className="rounded-2xl border border-stone-300 bg-white px-4 py-3">
                      <option value="train">train</option>
                      <option value="dev">dev</option>
                      <option value="test">test</option>
                      <option value="unassigned">unassigned</option>
                    </select>
                    <select name="quality_status" defaultValue={selectedExample.quality_status} className="rounded-2xl border border-stone-300 bg-white px-4 py-3">
                      <option value="accepted">accepted</option>
                      <option value="unchecked">unchecked</option>
                      <option value="needs_review">needs_review</option>
                      <option value="rejected">rejected</option>
                    </select>
                  </div>
                  <textarea
                    name="expected_output_json"
                    rows={8}
                    defaultValue={JSON.stringify(selectedExample.expected_output_json, null, 2)}
                    className="rounded-3xl border border-stone-300 bg-white px-4 py-3 font-mono text-sm"
                  />
                  <button className="rounded-3xl bg-sky-700 px-5 py-3 text-sm font-medium text-white" type="submit">
                    {t("datasets.editor.saveExample")}
                  </button>
                </form>
              ) : (
                <JsonView value={null} emptyLabel={t("datasets.editor.selectedExampleEmpty")} />
              )}
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold text-stone-900">{t("datasets.editor.selectedDataset")}</h3>
              <JsonView value={selectedDataset} emptyLabel={t("datasets.editor.selectedDatasetEmpty")} />
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold text-stone-900">{t("datasets.editor.qualityReport")}</h3>
              <JsonView value={qualityReport} emptyLabel={t("datasets.editor.qualityReportEmpty")} />
            </div>
          </div>
        </Panel>
      </div>
    </AppShell>
  );
}
