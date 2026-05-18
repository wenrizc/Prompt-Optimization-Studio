"use client";

import { FormEvent, useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { JsonView } from "@/components/json-view";
import { Panel } from "@/components/panel";
import { StatusChip } from "@/components/status-chip";
import { useI18n } from "@/lib/i18n/provider";
import { api } from "@/lib/api";
import { asTextareaValue, readJson, toErrorMessage } from "@/lib/studio";
import { useStudioWorkspace } from "@/lib/use-studio-workspace";

const defaultInputSchema = {
  type: "object",
  properties: { text: { type: "string" } },
  required: ["text"],
};

const defaultOutputSchema = {
  type: "object",
  properties: { label: { type: "string" } },
  required: ["label"],
};

export default function ProjectsPage() {
  const { t } = useI18n();
  const {
    projects,
    selectedProjectId,
    setSelectedProjectId,
    refreshWorkspace,
    loading,
    error,
  } = useStudioWorkspace();
  const [submitError, setSubmitError] = useState("");
  const [submitSuccess, setSubmitSuccess] = useState("");
  const [creating, setCreating] = useState(false);

  const selectedProject = useMemo(
    () => projects.find((item) => item.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setCreating(true);
    setSubmitError("");
    setSubmitSuccess("");
    try {
      const created = await api.post("/api/v1/projects", {
        name: form.get("name"),
        description: form.get("description"),
        task_kind: form.get("task_kind"),
        task_key: form.get("task_key"),
        task_display_name: form.get("task_display_name"),
        task_description: form.get("task_description"),
        input_schema_json: readJson(String(form.get("input_schema_json") ?? ""), defaultInputSchema),
        output_schema_json: readJson(String(form.get("output_schema_json") ?? ""), defaultOutputSchema),
        default_metric_config_json: readJson(
          String(form.get("default_metric_config_json") ?? ""),
          { metric: "json_field_accuracy", field: "label" },
        ),
        task_definition_json: readJson(String(form.get("task_definition_json") ?? ""), {}),
        report_profile_json: readJson(String(form.get("report_profile_json") ?? ""), {}),
      });
      setSubmitSuccess(t("projects.createdMessage", { id: (created as { id: number }).id }));
      await refreshWorkspace();
      setSelectedProjectId((created as { id: number }).id);
      event.currentTarget.reset();
    } catch (submissionError) {
      setSubmitError(toErrorMessage(submissionError));
    } finally {
      setCreating(false);
    }
  }

  return (
    <AppShell>
      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Panel
          title={t("projects.registryTitle")}
          description={t("projects.registryDescription")}
        >
          <form onSubmit={onSubmit} className="grid gap-4">
            <div className="grid gap-4 md:grid-cols-2">
              <input name="name" placeholder={t("projects.namePlaceholder")} className="rounded-2xl border border-stone-300 bg-white px-4 py-3" />
              <select name="task_kind" defaultValue="builtin" className="rounded-2xl border border-stone-300 bg-white px-4 py-3">
                <option value="builtin">{t("projects.taskKindBuiltin")}</option>
                <option value="custom">{t("projects.taskKindCustom")}</option>
              </select>
              <input name="task_key" defaultValue="classification" className="rounded-2xl border border-stone-300 bg-white px-4 py-3" />
              <input name="task_display_name" defaultValue={t("projects.taskDisplayName")} className="rounded-2xl border border-stone-300 bg-white px-4 py-3" />
            </div>
            <textarea name="description" rows={3} placeholder={t("projects.descriptionPlaceholder")} className="rounded-3xl border border-stone-300 bg-white px-4 py-3" />
            <textarea name="task_description" rows={3} placeholder={t("projects.taskDescriptionPlaceholder")} className="rounded-3xl border border-stone-300 bg-white px-4 py-3" />
            <div className="grid gap-4 lg:grid-cols-2">
              <textarea name="input_schema_json" rows={8} defaultValue={asTextareaValue(defaultInputSchema)} className="rounded-3xl border border-stone-300 bg-white px-4 py-3 font-mono text-sm" />
              <textarea name="output_schema_json" rows={8} defaultValue={asTextareaValue(defaultOutputSchema)} className="rounded-3xl border border-stone-300 bg-white px-4 py-3 font-mono text-sm" />
            </div>
            <div className="grid gap-4 lg:grid-cols-3">
              <textarea name="default_metric_config_json" rows={6} defaultValue={asTextareaValue({ metric: "json_field_accuracy", field: "label" })} className="rounded-3xl border border-stone-300 bg-white px-4 py-3 font-mono text-sm" />
              <textarea name="task_definition_json" rows={6} defaultValue="{}" className="rounded-3xl border border-stone-300 bg-white px-4 py-3 font-mono text-sm" />
              <textarea name="report_profile_json" rows={6} defaultValue="{}" className="rounded-3xl border border-stone-300 bg-white px-4 py-3 font-mono text-sm" />
            </div>
            <button className="rounded-3xl bg-teal-700 px-5 py-3 text-sm font-medium text-white" disabled={creating} type="submit">
              {creating ? t("projects.creatingButton") : t("projects.createButton")}
            </button>
          </form>
          {submitSuccess ? <p className="mt-4 text-sm text-emerald-700">{submitSuccess}</p> : null}
          {submitError ? <p className="mt-4 text-sm text-rose-700">{submitError}</p> : null}
          {error ? <p className="mt-2 text-sm text-rose-700">{error}</p> : null}
        </Panel>

        <Panel
          title={t("projects.workspaceTitle")}
          description={t("projects.workspaceDescription")}
        >
          {loading ? <p className="text-sm text-stone-500">{t("common.loadingProjects")}</p> : null}
          <div className="grid gap-3">
            {projects.map((project) => (
              <button
                key={project.id}
                onClick={() => setSelectedProjectId(project.id)}
                className={`rounded-3xl border px-4 py-4 text-left transition ${
                  selectedProjectId === project.id
                    ? "border-teal-700 bg-teal-50"
                    : "border-stone-200 bg-white hover:border-stone-400"
                }`}
                type="button"
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-stone-900">
                      #{project.id} · {project.name}
                    </p>
                    <p className="mt-1 text-xs text-stone-500">
                      {project.task_display_name} · {project.task_key}
                    </p>
                  </div>
                  <StatusChip value={project.status} />
                </div>
              </button>
            ))}
          </div>
          <div className="mt-5">
            <h3 className="mb-2 text-sm font-semibold text-stone-900">{t("projects.selectedSnapshot")}</h3>
            <JsonView value={selectedProject} emptyLabel={t("projects.selectedEmpty")} />
          </div>
        </Panel>
      </div>
    </AppShell>
  );
}
