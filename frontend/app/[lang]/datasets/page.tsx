"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { JsonView } from "@/components/json-view";
import { Panel } from "@/components/panel";
import { StatusChip } from "@/components/status-chip";
import { WorkspacePicker } from "@/components/workspace-picker";
import { api } from "@/lib/api";
import { formatDatasetSourceLabel, formatSplitLabel } from "@/lib/i18n/labels";
import { useI18n } from "@/lib/i18n/provider";
import { Dataset, DatasetExample, readJson, toErrorMessage } from "@/lib/studio";
import { useStudioWorkspace } from "@/lib/use-studio-workspace";

type DatasetMode = "import" | "generate";

export default function DatasetsPage() {
  const { t } = useI18n();
  const {
    projects,
    datasets,
    prompts,
    selectedProjectId,
    selectedDatasetId,
    setSelectedProjectId,
    setSelectedDatasetId,
    refreshWorkspace,
  } = useStudioWorkspace();
  const [mode, setMode] = useState<DatasetMode>("import");
  const [response, setResponse] = useState<unknown>(null);
  const [examples, setExamples] = useState<DatasetExample[]>([]);
  const [qualityReport, setQualityReport] = useState<unknown>(null);
  const [selectedExampleId, setSelectedExampleId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [loadingState, setLoadingState] = useState(false);
  const [error, setError] = useState("");

  const selectedProject = useMemo(
    () => projects.find((item) => item.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );
  const selectedDataset = useMemo(
    () => datasets.find((item) => item.id === selectedDatasetId) ?? null,
    [datasets, selectedDatasetId],
  );
  const selectedExample = useMemo(
    () => examples.find((item) => item.id === selectedExampleId) ?? null,
    [examples, selectedExampleId],
  );
  const filteredDatasets = useMemo(
    () => (selectedProjectId ? datasets.filter((item) => item.project_id === selectedProjectId) : datasets),
    [datasets, selectedProjectId],
  );
  const previewRows = useMemo(
    () =>
      examples.slice(0, 12).map((item) => ({
        id: item.id,
        split: item.split,
        text: item.input_json.text,
      })),
    [examples],
  );

  async function loadDatasetState(datasetId: number) {
    setLoadingState(true);
    setError("");
    try {
      const [exampleResponse, qualityResponse] = await Promise.all([
        api.get<{ items: DatasetExample[] }>(`/api/v1/datasets/${datasetId}/examples?page_size=100`),
        api.get(`/api/v1/datasets/${datasetId}/quality-report`),
      ]);
      setExamples(exampleResponse.items);
      setQualityReport(qualityResponse);
      if (exampleResponse.items.length > 0) {
        setSelectedExampleId((current) => current ?? exampleResponse.items[0].id);
      }
    } catch (loadError) {
      setError(toErrorMessage(loadError));
    } finally {
      setLoadingState(false);
    }
  }

  useEffect(() => {
    if (selectedDatasetId) {
      void loadDatasetState(selectedDatasetId);
    } else {
      setExamples([]);
      setQualityReport(null);
      setSelectedExampleId(null);
    }
  }, [selectedDatasetId]);

  async function submitImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProjectId) {
      setError(t("datasets.import.selectProjectError"));
      return;
    }
    const form = new FormData(event.currentTarget);
    setSubmitting(true);
    setError("");
    try {
      const result = await api.post("/api/v1/datasets/import", {
        project_id: selectedProjectId,
        name: form.get("name"),
        file_format: form.get("file_format"),
        content: form.get("content"),
        input_field: form.get("input_field"),
        output_field: form.get("output_field"),
        split: form.get("split"),
        metadata_fields: [],
        schema_json: selectedProject?.input_schema_json ?? { type: "object" },
      });
      setResponse(result);
      await refreshWorkspace();
      setSelectedDatasetId((result as { dataset: { id: number } }).dataset.id);
    } catch (submissionError) {
      setError(toErrorMessage(submissionError));
    } finally {
      setSubmitting(false);
    }
  }

  async function submitGenerate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProjectId) {
      setError(t("datasets.generator.selectProjectError"));
      return;
    }
    const form = new FormData(event.currentTarget);
    setSubmitting(true);
    setError("");
    try {
      const result = await api.post<{ dataset: Dataset; generated_examples: number }>("/api/v1/datasets/generate", {
        project_id: selectedProjectId,
        name: form.get("name"),
        command: form.get("command"),
        count: Number(form.get("count")),
      });
      setResponse(result);
      await refreshWorkspace();
      setSelectedDatasetId(result.dataset.id);
    } catch (submissionError) {
      setError(toErrorMessage(submissionError));
    } finally {
      setSubmitting(false);
    }
  }

  async function splitDataset() {
    if (!selectedDatasetId) {
      return;
    }
    setLoadingState(true);
    setError("");
    try {
      await api.post(`/api/v1/datasets/${selectedDatasetId}/split`, {
        train_ratio: 0.6,
        dev_ratio: 0.2,
        test_ratio: 0.2,
      });
      await loadDatasetState(selectedDatasetId);
    } catch (splitError) {
      setError(toErrorMessage(splitError));
    } finally {
      setLoadingState(false);
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
        input_json: { text: form.get("text") },
        expected_output_json: readJson(String(form.get("expected_output_json") ?? "{}")),
      });
      await loadDatasetState(selectedDatasetId);
    } catch (updateError) {
      setError(toErrorMessage(updateError));
    }
  }

  return (
    <AppShell>
      <Panel title={t("datasets.hub.title")} description={t("datasets.hub.description")}>
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

      <div className="grid gap-6 xl:grid-cols-[1.08fr_0.92fr]">
        <Panel title={t("datasets.hub.prepareTitle")} description={t("datasets.hub.prepareDescription")}>
          <div className="mb-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => setMode("import")}
              className={`rounded-3xl px-5 py-3 text-sm font-medium ${
                mode === "import" ? "bg-stone-900 text-white" : "border border-stone-300 bg-white text-stone-800"
              }`}
            >
              {t("datasets.hub.importTab")}
            </button>
            <button
              type="button"
              onClick={() => setMode("generate")}
              className={`rounded-3xl px-5 py-3 text-sm font-medium ${
                mode === "generate" ? "bg-stone-900 text-white" : "border border-stone-300 bg-white text-stone-800"
              }`}
            >
              {t("datasets.hub.generateTab")}
            </button>
          </div>

          {mode === "import" ? (
            <form className="grid gap-4" onSubmit={submitImport}>
              <input name="name" defaultValue={t("datasets.import.defaultName")} className="rounded-2xl border border-stone-300 bg-white px-4 py-3" />
              <div className="grid gap-4 md:grid-cols-2">
                <select name="file_format" defaultValue="jsonl" className="rounded-2xl border border-stone-300 bg-white px-4 py-3">
                  <option value="jsonl">JSONL</option>
                  <option value="json">JSON</option>
                  <option value="csv">CSV</option>
                </select>
                <select name="split" defaultValue="test" className="rounded-2xl border border-stone-300 bg-white px-4 py-3">
                  <option value="train">{formatSplitLabel(t, "train")}</option>
                  <option value="dev">{formatSplitLabel(t, "dev")}</option>
                  <option value="test">{formatSplitLabel(t, "test")}</option>
                  <option value="unassigned">{formatSplitLabel(t, "unassigned")}</option>
                </select>
                <input name="input_field" defaultValue="text" className="rounded-2xl border border-stone-300 bg-white px-4 py-3" />
                <input name="output_field" defaultValue="expected_output" className="rounded-2xl border border-stone-300 bg-white px-4 py-3" />
              </div>
              <textarea
                name="content"
                defaultValue={t("datasets.import.sampleJsonl")}
                rows={14}
                className="rounded-3xl border border-stone-300 bg-white px-4 py-3 font-mono text-sm"
              />
              <button
                type="submit"
                disabled={submitting}
                className="rounded-3xl bg-teal-700 px-5 py-3 text-sm font-medium text-white disabled:opacity-60"
              >
                {submitting ? t("datasets.import.importingButton") : t("datasets.import.importButton")}
              </button>
            </form>
          ) : (
            <form onSubmit={submitGenerate} className="grid gap-4">
              <input name="name" defaultValue={t("datasets.generator.defaultName")} className="rounded-2xl border border-stone-300 bg-white px-4 py-3" />
              <textarea
                name="command"
                rows={7}
                defaultValue={t("datasets.generator.defaultCommand")}
                className="rounded-3xl border border-stone-300 bg-white px-4 py-3"
              />
              <input name="count" defaultValue="60" className="rounded-2xl border border-stone-300 bg-white px-4 py-3" />
              <button className="rounded-3xl bg-emerald-700 px-5 py-3 text-sm font-medium text-white" disabled={submitting} type="submit">
                {submitting ? t("datasets.generator.generatingButton") : t("datasets.generator.generateButton")}
              </button>
            </form>
          )}

          {error ? <p className="mt-4 text-sm text-rose-700">{error}</p> : null}
          <div className="mt-5">
            <h3 className="mb-2 text-sm font-semibold text-stone-900">{t("datasets.hub.lastActionTitle")}</h3>
            <JsonView value={response} emptyLabel={t("datasets.hub.lastActionEmpty")} />
          </div>
        </Panel>

        <Panel title={t("datasets.hub.listTitle")} description={t("datasets.hub.listDescription")}>
          <div className="grid gap-3">
            {filteredDatasets.map((dataset) => (
              <button
                key={dataset.id}
                onClick={() => setSelectedDatasetId(dataset.id)}
                type="button"
                className={`rounded-3xl border px-4 py-4 text-left ${
                  selectedDatasetId === dataset.id
                    ? "border-emerald-700 bg-emerald-50"
                    : "border-stone-200 bg-white"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-stone-900">
                      #{dataset.id} · {dataset.name}
                    </p>
                    <p className="mt-1 text-xs text-stone-500">
                      {formatDatasetSourceLabel(t, dataset.source_type)} · {dataset.generation_model ?? formatDatasetSourceLabel(t, "manual")}
                    </p>
                  </div>
                  <StatusChip value={dataset.status} />
                </div>
              </button>
            ))}
          </div>
          <div className="mt-5">
            <h3 className="mb-2 text-sm font-semibold text-stone-900">{t("datasets.hub.selectedDatasetTitle")}</h3>
            <JsonView value={selectedDataset} emptyLabel={t("datasets.hub.selectedDatasetEmpty")} />
          </div>
        </Panel>
      </div>

      <Panel title={t("datasets.hub.advancedTitle")} description={t("datasets.hub.advancedDescription")}>
        <details className="group rounded-[28px] border border-stone-900/10 bg-white p-5">
          <summary className="cursor-pointer list-none text-sm font-semibold text-stone-900">
            {t("datasets.hub.advancedToggle")}
          </summary>
          <div className="mt-5 grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
            <div>
              <div className="mb-4 flex flex-wrap gap-3">
                <button onClick={() => selectedDatasetId && void loadDatasetState(selectedDatasetId)} className="rounded-3xl bg-sky-700 px-5 py-3 text-sm font-medium text-white" type="button">
                  {t("datasets.editor.refreshExamples")}
                </button>
                <button onClick={() => void splitDataset()} className="rounded-3xl border border-stone-300 bg-white px-5 py-3 text-sm font-medium text-stone-800" type="button">
                  {t("datasets.editor.resplit")}
                </button>
              </div>
              {loadingState ? <p className="mb-4 text-sm text-stone-500">{t("common.loadingDatasetState")}</p> : null}
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
                      <div className="text-right text-xs text-stone-500">{formatSplitLabel(t, String(row.split))}</div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-4">
              <div>
                <h3 className="mb-2 text-sm font-semibold text-stone-900">{t("datasets.editor.selectedExampleEditor")}</h3>
                {selectedExample ? (
                  <form key={selectedExample.id} onSubmit={updateExample} className="grid gap-3 rounded-3xl border border-stone-200 bg-white p-4">
                    <input
                      name="text"
                      defaultValue={String(selectedExample.input_json.text ?? "")}
                      className="rounded-2xl border border-stone-300 bg-white px-4 py-3"
                    />
                    <select name="split" defaultValue={selectedExample.split} className="rounded-2xl border border-stone-300 bg-white px-4 py-3">
                      <option value="train">{formatSplitLabel(t, "train")}</option>
                      <option value="dev">{formatSplitLabel(t, "dev")}</option>
                      <option value="test">{formatSplitLabel(t, "test")}</option>
                      <option value="unassigned">{formatSplitLabel(t, "unassigned")}</option>
                    </select>
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
                <h3 className="mb-2 text-sm font-semibold text-stone-900">{t("datasets.editor.qualityReport")}</h3>
                <JsonView value={qualityReport} emptyLabel={t("datasets.editor.qualityReportEmpty")} />
              </div>
            </div>
          </div>
        </details>
      </Panel>
    </AppShell>
  );
}
