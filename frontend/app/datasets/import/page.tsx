"use client";

import { FormEvent, useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { JsonView } from "@/components/json-view";
import { Panel } from "@/components/panel";
import { WorkspacePicker } from "@/components/workspace-picker";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { toErrorMessage } from "@/lib/studio";
import { useStudioWorkspace } from "@/lib/use-studio-workspace";

export default function DatasetImportPage() {
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
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const selectedProject = useMemo(
    () => projects.find((item) => item.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
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
        quality_status: form.get("quality_status"),
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

  return (
    <AppShell>
      <Panel
        title={t("datasets.import.title")}
        description={t("datasets.import.description")}
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
        <Panel title={t("datasets.import.formTitle")} description={t("datasets.import.formDescription")}>
          <form className="grid gap-4" onSubmit={onSubmit}>
            <input name="name" defaultValue={t("datasets.import.defaultName")} className="rounded-2xl border border-stone-300 bg-white px-4 py-3" />
            <div className="grid gap-4 md:grid-cols-2">
              <select name="file_format" defaultValue="jsonl" className="rounded-2xl border border-stone-300 bg-white px-4 py-3">
                <option value="jsonl">JSONL</option>
                <option value="json">JSON</option>
                <option value="csv">CSV</option>
              </select>
              <select name="split" defaultValue="test" className="rounded-2xl border border-stone-300 bg-white px-4 py-3">
                <option value="train">train</option>
                <option value="dev">dev</option>
                <option value="test">test</option>
                <option value="unassigned">unassigned</option>
              </select>
              <input name="input_field" defaultValue="text" className="rounded-2xl border border-stone-300 bg-white px-4 py-3" />
              <input name="output_field" defaultValue="expected_output" className="rounded-2xl border border-stone-300 bg-white px-4 py-3" />
            </div>
            <select name="quality_status" defaultValue="accepted" className="rounded-2xl border border-stone-300 bg-white px-4 py-3">
              <option value="accepted">{t("common.status.accepted")}</option>
              <option value="unchecked">{t("common.status.unchecked")}</option>
              <option value="needs_review">{t("common.status.needs_review")}</option>
            </select>
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
          {error ? <p className="mt-4 text-sm text-rose-700">{error}</p> : null}
        </Panel>

        <Panel title={t("datasets.import.importResultTitle")} description={t("datasets.import.importResultDescription")}>
          <div className="space-y-4">
            <div>
              <h3 className="mb-2 text-sm font-semibold text-stone-900">{t("datasets.import.lastImportResponse")}</h3>
              <JsonView value={response} emptyLabel={t("datasets.import.lastImportResponseEmpty")} />
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold text-stone-900">{t("datasets.import.activeSchemas")}</h3>
              <JsonView
                value={{
                  input_schema_json: selectedProject?.input_schema_json,
                  output_schema_json: selectedProject?.output_schema_json,
                  default_metric_config_json: selectedProject?.default_metric_config_json,
                }}
                emptyLabel={t("datasets.import.activeSchemasEmpty")}
              />
            </div>
          </div>
        </Panel>
      </div>
    </AppShell>
  );
}
