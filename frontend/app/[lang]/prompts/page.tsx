"use client";

import { FormEvent, useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { JsonView } from "@/components/json-view";
import { Panel } from "@/components/panel";
import { WorkspacePicker } from "@/components/workspace-picker";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { asTextareaValue, toErrorMessage } from "@/lib/studio";
import { useStudioWorkspace } from "@/lib/use-studio-workspace";

export default function PromptsPage() {
  const { t } = useI18n();
  const {
    projects,
    datasets,
    prompts,
    selectedProjectId,
    selectedPromptId,
    setSelectedProjectId,
    setSelectedPromptId,
    refreshWorkspace,
  } = useStudioWorkspace();
  const [validationResult, setValidationResult] = useState<unknown>(null);
  const [submitState, setSubmitState] = useState("");
  const [error, setError] = useState("");

  const selectedProject = useMemo(
    () => projects.find((item) => item.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );
  const selectedPrompt = useMemo(
    () => prompts.find((item) => item.id === selectedPromptId) ?? null,
    [prompts, selectedPromptId],
  );
  const filteredPrompts = selectedProjectId
    ? prompts.filter((item) => item.project_id === selectedProjectId)
    : prompts;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const submitter = ((event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null)?.value ?? "save";
    setError("");
    if (submitter === "validate") {
      try {
        const result = await api.post("/api/v1/prompts/validate", {
          user_template: form.get("user_template"),
          input_schema_json: selectedProject?.input_schema_json ?? {
            type: "object",
            properties: { text: { type: "string" } },
            required: ["text"],
          },
          output_schema_json: selectedProject?.output_schema_json ?? { type: "object" },
        });
        setValidationResult(result);
      } catch (validationError) {
        setError(toErrorMessage(validationError));
      }
      return;
    }

    if (!selectedProjectId) {
      setError(t("common.selectProjectFirst"));
      return;
    }

    setSubmitState(t("prompts.saving"));
    try {
      const created = await api.post("/api/v1/prompts", {
        project_id: selectedProjectId,
        name: form.get("name"),
        system_prompt: form.get("system_prompt"),
        user_template: form.get("user_template"),
      });
      setSubmitState(t("prompts.saved", { id: (created as { id: number }).id }));
      await refreshWorkspace();
      setSelectedPromptId((created as { id: number }).id);
    } catch (submissionError) {
      setSubmitState("");
      setError(toErrorMessage(submissionError));
    }
  }

  return (
    <AppShell>
      <Panel
        title={t("prompts.title")}
        description={t("prompts.description")}
      >
        <WorkspacePicker
          projects={projects}
          datasets={datasets}
          prompts={prompts}
          selectedProjectId={selectedProjectId}
          selectedPromptId={selectedPromptId}
          onProjectChange={setSelectedProjectId}
          onPromptChange={setSelectedPromptId}
        />
      </Panel>

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <Panel title={t("prompts.createTitle")} description={t("prompts.createDescription")}>
          <form onSubmit={handleSubmit} className="grid gap-4">
            <input name="name" defaultValue={selectedPrompt?.name ?? t("prompts.promptNameDefault")} className="rounded-2xl border border-stone-300 bg-white px-4 py-3" />
            <textarea
              name="system_prompt"
              rows={7}
              defaultValue={selectedPrompt?.system_prompt ?? t("prompts.defaultSystemPrompt")}
              className="rounded-3xl border border-stone-300 bg-white px-4 py-3"
            />
            <textarea
              name="user_template"
              rows={6}
              defaultValue={selectedPrompt?.user_template ?? t("prompts.defaultUserTemplate")}
              className="rounded-3xl border border-stone-300 bg-white px-4 py-3 font-mono text-sm"
            />
            <textarea
              name="output_schema_json"
              rows={10}
              defaultValue={asTextareaValue(selectedPrompt?.output_schema_json ?? selectedProject?.output_schema_json ?? { type: "object" })}
              readOnly
              className="rounded-3xl border border-stone-300 bg-stone-50 px-4 py-3 font-mono text-sm text-stone-700"
            />
            <div className="flex flex-wrap gap-3">
              <button className="rounded-3xl bg-amber-700 px-5 py-3 text-sm font-medium text-white" type="submit" value="save">
                {t("prompts.saveButton")}
              </button>
              <button className="rounded-3xl border border-stone-300 bg-white px-5 py-3 text-sm font-medium text-stone-800" type="submit" value="validate">
                {t("prompts.validateButton")}
              </button>
            </div>
          </form>
          {submitState ? <p className="mt-4 text-sm text-emerald-700">{submitState}</p> : null}
          {error ? <p className="mt-4 text-sm text-rose-700">{error}</p> : null}
        </Panel>

        <Panel title={t("prompts.inventoryTitle")} description={t("prompts.inventoryDescription")}>
          <div className="grid gap-3">
            {filteredPrompts.map((prompt) => (
              <button
                key={prompt.id}
                onClick={() => setSelectedPromptId(prompt.id)}
                type="button"
                className={`rounded-3xl border px-4 py-4 text-left ${
                  selectedPromptId === prompt.id
                    ? "border-amber-700 bg-amber-50"
                    : "border-stone-200 bg-white"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-stone-900">
                      #{prompt.id} · {prompt.name} v{prompt.version}
                    </p>
                    <p className="mt-1 text-xs text-stone-500">{prompt.user_template.slice(0, 90)}</p>
                  </div>
                </div>
              </button>
            ))}
          </div>
          <div className="mt-5 space-y-4">
            <div>
              <h3 className="mb-2 text-sm font-semibold text-stone-900">{t("prompts.selectedPrompt")}</h3>
              <JsonView value={selectedPrompt} emptyLabel={t("prompts.selectedPromptEmpty")} />
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold text-stone-900">{t("prompts.validationOutput")}</h3>
              <JsonView value={validationResult} emptyLabel={t("prompts.validationError")} />
            </div>
          </div>
        </Panel>
      </div>
    </AppShell>
  );
}
