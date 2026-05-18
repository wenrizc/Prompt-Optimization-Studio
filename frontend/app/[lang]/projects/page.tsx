"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { JsonView } from "@/components/json-view";
import { Panel } from "@/components/panel";
import { StatusChip } from "@/components/status-chip";
import { useI18n } from "@/lib/i18n/provider";
import { api } from "@/lib/api";
import { BuiltinTaskTemplate, CustomTaskTemplate, toErrorMessage } from "@/lib/studio";
import { useStudioWorkspace } from "@/lib/use-studio-workspace";

type ProjectFormState = {
  name: string;
  description: string;
  taskKind: "builtin" | "custom";
  builtinTaskKey: string;
  customTemplateId: number | null;
};

function toReadonlyTemplate(template: BuiltinTaskTemplate | CustomTaskTemplate) {
  return {
    task_key: template.task_key,
    task_display_name: template.task_display_name,
    task_description: template.task_description,
    input_schema_json: template.input_schema_json,
    output_schema_json: template.output_schema_json,
    default_metric_config_json: template.default_metric_config_json,
    task_definition_json: template.task_definition_json,
    report_profile_json: template.report_profile_json,
  };
}

export default function ProjectsPage() {
  const { t, tm, locale, href } = useI18n();
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
  const [builtinTasks, setBuiltinTasks] = useState<BuiltinTaskTemplate[]>([]);
  const [customTemplates, setCustomTemplates] = useState<CustomTaskTemplate[]>([]);
  const [catalogError, setCatalogError] = useState("");
  const builtinTaskText = tm<
    Record<string, { taskDisplayName: string; taskDescription: string }>
  >("projects.builtinTaskText");
  const fallbackBuiltinTask = useMemo<BuiltinTaskTemplate>(
    () => ({
      task_key: "qa",
      task_display_name: builtinTaskText.qa.taskDisplayName,
      task_description: builtinTaskText.qa.taskDescription,
      input_schema_json: {
        type: "object",
        properties: { text: { type: "string" } },
        required: ["text"],
      },
      output_schema_json: {
        type: "object",
        properties: { answer: { type: "string" } },
        required: ["answer"],
      },
      default_metric_config_json: {
        metric: "f1_token",
        field: "answer",
        correct_threshold: 0.8,
      },
      task_definition_json: {
        task_family: "qa",
        target_field: "answer",
        grounded: true,
        answer_style: "concise",
      },
      report_profile_json: {
        task_family: "qa",
        primary_output_field: "answer",
        focus_areas: ["answer_overlap", "hallucination_risk", "coverage"],
      },
    }),
    [builtinTaskText],
  );
  const [formState, setFormState] = useState<ProjectFormState>({
    name: "",
    description: "",
    taskKind: "builtin",
    builtinTaskKey: fallbackBuiltinTask.task_key,
    customTemplateId: null,
  });

  const selectedProject = useMemo(
    () => projects.find((item) => item.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );
  const availableBuiltinTasks = builtinTasks.length ? builtinTasks : [fallbackBuiltinTask];
  const selectedBuiltinTask =
    availableBuiltinTasks.find((item) => item.task_key === formState.builtinTaskKey) ??
    availableBuiltinTasks[0] ??
    fallbackBuiltinTask;
  const selectedCustomTemplate =
    customTemplates.find((item) => item.id === formState.customTemplateId) ??
    customTemplates[0] ??
    null;
  const selectedTemplate = formState.taskKind === "builtin" ? selectedBuiltinTask : selectedCustomTemplate;

  useEffect(() => {
    async function loadBuiltinTasks() {
      try {
        const response = await api.get<{ items: BuiltinTaskTemplate[] }>(
          `/api/v1/projects/builtin-tasks?locale=${locale}`,
        );
        setBuiltinTasks(response.items);
        setCatalogError("");
      } catch (loadError) {
        setCatalogError(toErrorMessage(loadError));
      }
    }

    void loadBuiltinTasks();
  }, [locale]);

  useEffect(() => {
    async function loadCustomTemplates() {
      try {
        const response = await api.get<{ items: CustomTaskTemplate[] }>(
          "/api/v1/custom-task-templates",
        );
        setCustomTemplates(response.items);
        if (!formState.customTemplateId && response.items[0]) {
          setFormState((current) => ({
            ...current,
            customTemplateId: response.items[0].id,
          }));
        }
      } catch (loadError) {
        setCatalogError(toErrorMessage(loadError));
      }
    }

    void loadCustomTemplates();
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreating(true);
    setSubmitError("");
    setSubmitSuccess("");

    if (!selectedTemplate) {
      setSubmitError(t("projects.customTemplateRequired"));
      setCreating(false);
      return;
    }

    try {
      const created = await api.post("/api/v1/projects", {
        name: formState.name,
        description: formState.description || null,
        task_kind: formState.taskKind,
        task_key: selectedTemplate.task_key,
        template_locale: locale,
        task_display_name: selectedTemplate.task_display_name,
        task_description: selectedTemplate.task_description || null,
        input_schema_json: selectedTemplate.input_schema_json,
        output_schema_json: selectedTemplate.output_schema_json,
        default_metric_config_json: selectedTemplate.default_metric_config_json,
        task_definition_json: selectedTemplate.task_definition_json,
        report_profile_json: selectedTemplate.report_profile_json,
      });
      setSubmitSuccess(t("projects.createdMessage", { id: (created as { id: number }).id }));
      await refreshWorkspace();
      setSelectedProjectId((created as { id: number }).id);
      setFormState((current) => ({
        ...current,
        name: "",
        description: "",
      }));
    } catch (submissionError) {
      setSubmitError(toErrorMessage(submissionError));
    } finally {
      setCreating(false);
    }
  }

  return (
    <AppShell>
      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Panel title={t("projects.registryTitle")} description={t("projects.registryDescription")}>
          <form onSubmit={onSubmit} className="grid gap-4">
            <div className="grid gap-4 md:grid-cols-2">
              <input
                name="name"
                placeholder={t("projects.namePlaceholder")}
                value={formState.name}
                onChange={(event) =>
                  setFormState((current) => ({ ...current, name: event.target.value }))
                }
                className="rounded-2xl border border-stone-300 bg-white px-4 py-3"
              />
              <select
                name="task_kind"
                value={formState.taskKind}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    taskKind: event.target.value as "builtin" | "custom",
                  }))
                }
                className="rounded-2xl border border-stone-300 bg-white px-4 py-3"
              >
                <option value="builtin">{t("projects.taskKindBuiltin")}</option>
                <option value="custom">{t("projects.taskKindCustom")}</option>
              </select>
              {formState.taskKind === "builtin" ? (
                <select
                  name="builtin_task_key"
                  value={formState.builtinTaskKey}
                  onChange={(event) =>
                    setFormState((current) => ({
                      ...current,
                      builtinTaskKey: event.target.value,
                    }))
                  }
                  className="rounded-2xl border border-stone-300 bg-white px-4 py-3 md:col-span-2"
                >
                  {availableBuiltinTasks.map((task) => (
                    <option key={task.task_key} value={task.task_key}>
                      {task.task_key} · {task.task_display_name}
                    </option>
                  ))}
                </select>
              ) : (
                <div className="grid gap-3 md:col-span-2">
                  <select
                    name="custom_template_id"
                    value={selectedCustomTemplate?.id ?? ""}
                    onChange={(event) =>
                      setFormState((current) => ({
                        ...current,
                        customTemplateId: Number(event.target.value),
                      }))
                    }
                    className="rounded-2xl border border-stone-300 bg-white px-4 py-3"
                  >
                    {customTemplates.map((template) => (
                      <option key={template.id} value={template.id}>
                        {template.task_key} · {template.task_display_name}
                      </option>
                    ))}
                  </select>
                  {customTemplates.length ? null : (
                    <div className="rounded-3xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                      <p>{t("projects.customTemplateEmpty")}</p>
                      <Link
                        href={href("/custom-tasks")}
                        className="mt-2 inline-flex rounded-full border border-amber-300 px-3 py-1 text-xs font-medium text-amber-900"
                      >
                        {t("projects.customTasksLink")}
                      </Link>
                    </div>
                  )}
                </div>
              )}
            </div>
            <textarea
              name="description"
              rows={3}
              placeholder={t("projects.descriptionPlaceholder")}
              value={formState.description}
              onChange={(event) =>
                setFormState((current) => ({ ...current, description: event.target.value }))
              }
              className="rounded-3xl border border-stone-300 bg-white px-4 py-3"
            />
            <div className="rounded-3xl border border-stone-200 bg-stone-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-stone-900">
                    {t("projects.readonlyConfigTitle")}
                  </h3>
                  <p className="mt-1 text-sm text-stone-500">
                    {formState.taskKind === "builtin"
                      ? t("projects.readonlyBuiltinHint")
                      : t("projects.readonlyCustomHint")}
                  </p>
                </div>
                {formState.taskKind === "custom" ? (
                  <Link
                    href={href("/custom-tasks")}
                    className="rounded-full border border-stone-300 px-3 py-1 text-xs font-medium text-stone-700"
                  >
                    {t("projects.customTasksLink")}
                  </Link>
                ) : null}
              </div>
              <div className="mt-4 grid gap-4">
                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">
                    {t("projects.taskSummaryLabel")}
                  </p>
                  <div className="rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm text-stone-700">
                    {selectedTemplate
                      ? `${selectedTemplate.task_key} · ${selectedTemplate.task_display_name}`
                      : t("projects.selectedEmpty")}
                  </div>
                </div>
                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">
                    {t("projects.taskDescriptionLabel")}
                  </p>
                  <div className="rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm text-stone-700">
                    {selectedTemplate?.task_description || t("common.noData")}
                  </div>
                </div>
                <div className="grid gap-4 lg:grid-cols-2">
                  <div>
                    <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">
                      `input_schema_json`
                    </p>
                    <JsonView value={selectedTemplate?.input_schema_json ?? null} />
                  </div>
                  <div>
                    <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">
                      `output_schema_json`
                    </p>
                    <JsonView value={selectedTemplate?.output_schema_json ?? null} />
                  </div>
                </div>
                <div className="grid gap-4 lg:grid-cols-3">
                  <div>
                    <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">
                      `default_metric_config_json`
                    </p>
                    <JsonView value={selectedTemplate?.default_metric_config_json ?? null} />
                  </div>
                  <div>
                    <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">
                      `task_definition_json`
                    </p>
                    <JsonView value={selectedTemplate?.task_definition_json ?? null} />
                  </div>
                  <div>
                    <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">
                      `report_profile_json`
                    </p>
                    <JsonView value={selectedTemplate?.report_profile_json ?? null} />
                  </div>
                </div>
              </div>
            </div>
            <button
              className="rounded-3xl bg-teal-700 px-5 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
              disabled={creating || !selectedTemplate}
              type="submit"
            >
              {creating ? t("projects.creatingButton") : t("projects.createButton")}
            </button>
          </form>
          {submitSuccess ? <p className="mt-4 text-sm text-emerald-700">{submitSuccess}</p> : null}
          {submitError ? <p className="mt-4 text-sm text-rose-700">{submitError}</p> : null}
          {catalogError ? <p className="mt-2 text-sm text-amber-700">{catalogError}</p> : null}
          {error ? <p className="mt-2 text-sm text-rose-700">{error}</p> : null}
        </Panel>

        <Panel title={t("projects.workspaceTitle")} description={t("projects.workspaceDescription")}>
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
                      {project.task_key} · {project.task_display_name}
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
