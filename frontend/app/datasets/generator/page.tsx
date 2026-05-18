"use client";

import { FormEvent, useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { JsonView } from "@/components/json-view";
import { Panel } from "@/components/panel";
import { StatusChip } from "@/components/status-chip";
import { WorkspacePicker } from "@/components/workspace-picker";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { DEFAULT_GENERATION_MODEL, Dataset, toErrorMessage } from "@/lib/studio";
import { useStudioWorkspace } from "@/lib/use-studio-workspace";

export default function DatasetGeneratorPage() {
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
  const [response, setResponse] = useState<unknown>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const generatedDatasets = useMemo(
    () => (selectedProjectId ? datasets.filter((item) => item.project_id === selectedProjectId) : datasets),
    [datasets, selectedProjectId],
  );
  const selectedDataset = useMemo(
    () => datasets.find((item) => item.id === selectedDatasetId) ?? null,
    [datasets, selectedDatasetId],
  );

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
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
        generation_model: form.get("generation_model"),
        quality_status: form.get("quality_status"),
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

  return (
    <AppShell>
      <Panel
        title={t("datasets.generator.title")}
        description={t("datasets.generator.description")}
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

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Panel title={t("datasets.generator.formTitle")} description={t("datasets.generator.formDescription")}>
          <form onSubmit={onSubmit} className="grid gap-4">
            <input name="name" defaultValue={t("datasets.generator.defaultName")} className="rounded-2xl border border-stone-300 bg-white px-4 py-3" />
            <textarea
              name="command"
              rows={7}
              defaultValue={t("datasets.generator.defaultCommand")}
              className="rounded-3xl border border-stone-300 bg-white px-4 py-3"
            />
            <div className="grid gap-4 md:grid-cols-3">
              <input name="count" defaultValue="60" className="rounded-2xl border border-stone-300 bg-white px-4 py-3" />
              <input name="generation_model" defaultValue={DEFAULT_GENERATION_MODEL} className="rounded-2xl border border-stone-300 bg-white px-4 py-3" />
              <select name="quality_status" defaultValue="unchecked" className="rounded-2xl border border-stone-300 bg-white px-4 py-3">
                <option value="unchecked">{t("common.status.unchecked")}</option>
                <option value="accepted">{t("common.status.accepted")}</option>
                <option value="needs_review">{t("common.status.needs_review")}</option>
              </select>
            </div>
            <button className="rounded-3xl bg-emerald-700 px-5 py-3 text-sm font-medium text-white" disabled={submitting} type="submit">
              {submitting ? t("datasets.generator.generatingButton") : t("datasets.generator.generateButton")}
            </button>
          </form>
          {error ? <p className="mt-4 text-sm text-rose-700">{error}</p> : null}
          <div className="mt-5">
            <h3 className="mb-2 text-sm font-semibold text-stone-900">{t("datasets.generator.lastResponse")}</h3>
            <JsonView value={response} emptyLabel={t("datasets.generator.lastResponseEmpty")} />
          </div>
        </Panel>

        <Panel title={t("datasets.generator.listTitle")} description={t("datasets.generator.listDescription")}>
          <div className="grid gap-3">
            {generatedDatasets.map((dataset) => (
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
                      {dataset.source_type} · {dataset.generation_model ?? "manual"}
                    </p>
                  </div>
                  <StatusChip value={dataset.status} />
                </div>
              </button>
            ))}
          </div>
          <div className="mt-5">
            <h3 className="mb-2 text-sm font-semibold text-stone-900">{t("datasets.generator.selectedSnapshot")}</h3>
            <JsonView value={selectedDataset} emptyLabel={t("datasets.generator.selectedEmpty")} />
          </div>
        </Panel>
      </div>
    </AppShell>
  );
}
