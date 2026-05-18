"use client";

import { FormEvent, ReactNode, useEffect, useMemo, useRef, useState, WheelEvent } from "react";

import { AppShell } from "@/components/app-shell";
import { JsonView } from "@/components/json-view";
import { Panel } from "@/components/panel";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import {
  asTextareaValue,
  CustomTaskTemplate,
  CustomTaskTemplateGuidanceItem,
  GeneratedCustomTaskTemplateDraft,
  readJson,
  toErrorMessage,
} from "@/lib/studio";

type TemplateFormState = {
  taskKey: string;
  taskDisplayName: string;
  taskDescription: string;
  inputSchemaJson: string;
  outputSchemaJson: string;
  defaultMetricConfigJson: string;
  taskDefinitionJson: string;
  reportProfileJson: string;
};

type ConfigStepId =
  | "task_identity"
  | "input_schema_json"
  | "output_schema_json"
  | "default_metric_config_json"
  | "task_definition_json"
  | "report_profile_json";

type ConfigStepDefinition = {
  id: ConfigStepId;
  title: string;
  summary: string;
  configurableFields: string[];
  downstreamUsage: string[];
  examples: string[];
  badge: string;
};

type DraftReviewState = {
  bundle: GeneratedCustomTaskTemplateDraft;
  acceptedStepIds: ConfigStepId[];
};

type DetailCard = {
  id: string;
  title: string;
  content: ReactNode;
};

function buildFormState(template: CustomTaskTemplate): TemplateFormState {
  return {
    taskKey: template.task_key,
    taskDisplayName: template.task_display_name,
    taskDescription: template.task_description ?? "",
    inputSchemaJson: asTextareaValue(template.input_schema_json),
    outputSchemaJson: asTextareaValue(template.output_schema_json),
    defaultMetricConfigJson: asTextareaValue(template.default_metric_config_json),
    taskDefinitionJson: asTextareaValue(template.task_definition_json),
    reportProfileJson: asTextareaValue(template.report_profile_json),
  };
}

function buildEmptyFormState(): TemplateFormState {
  return {
    taskKey: "custom_task",
    taskDisplayName: "Custom Task",
    taskDescription: "",
    inputSchemaJson: asTextareaValue({
      type: "object",
      properties: { text: { type: "string" } },
      required: ["text"],
    }),
    outputSchemaJson: asTextareaValue({
      type: "object",
      properties: { answer: { type: "string" } },
      required: ["answer"],
    }),
    defaultMetricConfigJson: asTextareaValue({
      metric: "f1_token",
      field: "answer",
      correct_threshold: 0.8,
    }),
    taskDefinitionJson: asTextareaValue({
      task_family: "custom",
      target_field: "answer",
    }),
    reportProfileJson: asTextareaValue({
      task_family: "custom",
      primary_output_field: "answer",
      focus_areas: ["correctness"],
    }),
  };
}

function parseJsonObject(fieldName: string, text: string): Record<string, unknown> {
  const parsed = JSON.parse(text);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${fieldName} must be a JSON object`);
  }
  return parsed as Record<string, unknown>;
}

function buildStepDefinitions(t: (key: string, vars?: Record<string, string | number>) => string): ConfigStepDefinition[] {
  return [
    {
      id: "task_identity",
      title: t("customTasks.steps.taskIdentity.title"),
      summary: t("customTasks.steps.taskIdentity.summary"),
      configurableFields: ["task_key", "task_display_name", "task_description"],
      downstreamUsage: [
        t("customTasks.steps.taskIdentity.usage1"),
        t("customTasks.steps.taskIdentity.usage2"),
        t("customTasks.steps.taskIdentity.usage3"),
      ],
      examples: [
        'task_key: "customer_support_qa"',
        'task_display_name: "客服问答"',
        'task_description: "基于用户输入回答客服类问题，输出简洁答案。"',
      ],
      badge: "01",
    },
    {
      id: "input_schema_json",
      title: t("customTasks.steps.inputSchema.title"),
      summary: t("customTasks.steps.inputSchema.summary"),
      configurableFields: ["type", "properties", "required", "items", "enum"],
      downstreamUsage: [
        t("customTasks.steps.inputSchema.usage1"),
        t("customTasks.steps.inputSchema.usage2"),
        t("customTasks.steps.inputSchema.usage3"),
      ],
      examples: [
        '{ "type": "object", "properties": { "text": { "type": "string" } }, "required": ["text"] }',
      ],
      badge: "02",
    },
    {
      id: "output_schema_json",
      title: t("customTasks.steps.outputSchema.title"),
      summary: t("customTasks.steps.outputSchema.summary"),
      configurableFields: ["type", "properties", "required", "enum"],
      downstreamUsage: [
        t("customTasks.steps.outputSchema.usage1"),
        t("customTasks.steps.outputSchema.usage2"),
        t("customTasks.steps.outputSchema.usage3"),
      ],
      examples: [
        '{ "type": "object", "properties": { "answer": { "type": "string" } }, "required": ["answer"] }',
      ],
      badge: "03",
    },
    {
      id: "default_metric_config_json",
      title: t("customTasks.steps.metric.title"),
      summary: t("customTasks.steps.metric.summary"),
      configurableFields: ["metric", "field", "correct_threshold", "fields", "pass_threshold"],
      downstreamUsage: [
        t("customTasks.steps.metric.usage1"),
        t("customTasks.steps.metric.usage2"),
        t("customTasks.steps.metric.usage3"),
      ],
      examples: [
        '{ "metric": "f1_token", "field": "answer", "correct_threshold": 0.8 }',
        '{ "metric": "json_field_accuracy", "field": "result" }',
      ],
      badge: "04",
    },
    {
      id: "task_definition_json",
      title: t("customTasks.steps.taskDefinition.title"),
      summary: t("customTasks.steps.taskDefinition.summary"),
      configurableFields: ["task_family", "target_field", "grounded", "answer_style"],
      downstreamUsage: [
        t("customTasks.steps.taskDefinition.usage1"),
        t("customTasks.steps.taskDefinition.usage2"),
        t("customTasks.steps.taskDefinition.usage3"),
      ],
      examples: [
        '{ "task_family": "custom", "target_field": "answer" }',
        '{ "task_family": "custom", "target_field": "label", "grounded": false }',
      ],
      badge: "05",
    },
    {
      id: "report_profile_json",
      title: t("customTasks.steps.reportProfile.title"),
      summary: t("customTasks.steps.reportProfile.summary"),
      configurableFields: ["task_family", "primary_output_field", "focus_areas"],
      downstreamUsage: [
        t("customTasks.steps.reportProfile.usage1"),
        t("customTasks.steps.reportProfile.usage2"),
        t("customTasks.steps.reportProfile.usage3"),
      ],
      examples: [
        '{ "task_family": "custom", "primary_output_field": "answer", "focus_areas": ["correctness"] }',
      ],
      badge: "06",
    },
  ];
}

function buildPayload(formState: TemplateFormState) {
  return {
    task_key: formState.taskKey.trim(),
    task_display_name: formState.taskDisplayName.trim(),
    task_description: formState.taskDescription.trim() || null,
    input_schema_json: parseJsonObject("input_schema_json", formState.inputSchemaJson),
    output_schema_json: parseJsonObject("output_schema_json", formState.outputSchemaJson),
    default_metric_config_json: parseJsonObject(
      "default_metric_config_json",
      formState.defaultMetricConfigJson,
    ),
    task_definition_json: parseJsonObject("task_definition_json", formState.taskDefinitionJson),
    report_profile_json: parseJsonObject("report_profile_json", formState.reportProfileJson),
  };
}

function buildLivePreview(formState: TemplateFormState) {
  return {
    task_key: formState.taskKey.trim(),
    task_display_name: formState.taskDisplayName.trim(),
    task_description: formState.taskDescription.trim() || null,
    input_schema_json: readJson(formState.inputSchemaJson),
    output_schema_json: readJson(formState.outputSchemaJson),
    default_metric_config_json: readJson(formState.defaultMetricConfigJson),
    task_definition_json: readJson(formState.taskDefinitionJson),
    report_profile_json: readJson(formState.reportProfileJson),
  };
}

function getDraftGuidanceItem(
  draftReview: DraftReviewState | null,
  stepId: ConfigStepId,
): CustomTaskTemplateGuidanceItem | null {
  if (!draftReview) {
    return null;
  }
  return draftReview.bundle.guidance.items[stepId] ?? null;
}

export default function CustomTasksPage() {
  const { t } = useI18n();
  const stepDefinitions = useMemo(() => buildStepDefinitions(t), [t]);
  const [templates, setTemplates] = useState<CustomTaskTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [formState, setFormState] = useState<TemplateFormState>(() => buildEmptyFormState());
  const [submitMessage, setSubmitMessage] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [activeStepIndex, setActiveStepIndex] = useState(0);
  const [activeDetailIndex, setActiveDetailIndex] = useState(0);
  const [draftPrompt, setDraftPrompt] = useState("");
  const [isGeneratingDraft, setIsGeneratingDraft] = useState(false);
  const [draftReview, setDraftReview] = useState<DraftReviewState | null>(null);
  const wheelLockRef = useRef(0);

  useEffect(() => {
    async function loadTemplates() {
      try {
        const response = await api.get<{ items: CustomTaskTemplate[] }>(
          "/api/v1/custom-task-templates",
        );
        setTemplates(response.items);
        if (response.items[0]) {
          setSelectedTemplateId(response.items[0].id);
          setFormState(buildFormState(response.items[0]));
        }
      } catch (error) {
        setSubmitError(toErrorMessage(error));
      }
    }

    void loadTemplates();
  }, []);

  const selectedTemplate = useMemo(
    () => templates.find((item) => item.id === selectedTemplateId) ?? null,
    [selectedTemplateId, templates],
  );
  const activeStep = stepDefinitions[activeStepIndex] ?? stepDefinitions[0];
  const draftGuidanceItem = getDraftGuidanceItem(draftReview, activeStep.id);

  function loadTemplate(template: CustomTaskTemplate) {
    setSelectedTemplateId(template.id);
    setFormState(buildFormState(template));
    setDraftReview(null);
    setSubmitMessage("");
    setSubmitError("");
  }

  function resetToNewTemplate() {
    setSelectedTemplateId(null);
    setFormState(buildEmptyFormState());
    setDraftReview(null);
    setSubmitMessage("");
    setSubmitError("");
  }

  function moveToStep(nextIndex: number) {
    const clamped = Math.max(0, Math.min(stepDefinitions.length - 1, nextIndex));
    setActiveStepIndex(clamped);
    setActiveDetailIndex(0);
  }

  function handleWheel(event: WheelEvent<HTMLDivElement>) {
    const now = Date.now();
    if (now - wheelLockRef.current < 220) {
      return;
    }
    if (Math.abs(event.deltaY) < 12) {
      return;
    }
    event.preventDefault();
    wheelLockRef.current = now;
    setActiveDetailIndex((current) => {
      const direction = event.deltaY > 0 ? 1 : -1;
      const nextDetailIndex = current + direction;
      if (nextDetailIndex < 0) {
        moveToStep(activeStepIndex - 1);
        return 0;
      }
      if (nextDetailIndex >= detailCards.length) {
        moveToStep(activeStepIndex + 1);
        return 0;
      }
      return nextDetailIndex;
    });
  }

  function updateStepJson(stepId: ConfigStepId, value: string) {
    setFormState((current) => {
      if (stepId === "input_schema_json") {
        return { ...current, inputSchemaJson: value };
      }
      if (stepId === "output_schema_json") {
        return { ...current, outputSchemaJson: value };
      }
      if (stepId === "default_metric_config_json") {
        return { ...current, defaultMetricConfigJson: value };
      }
      if (stepId === "task_definition_json") {
        return { ...current, taskDefinitionJson: value };
      }
      return { ...current, reportProfileJson: value };
    });
  }

  function applyDraftStep(stepId: ConfigStepId) {
    if (!draftReview) {
      return;
    }
    const draft = draftReview.bundle.draft;
    setFormState((current) => {
      if (stepId === "task_identity") {
        return {
          ...current,
          taskKey: draft.task_key,
          taskDisplayName: draft.task_display_name,
          taskDescription: draft.task_description ?? "",
        };
      }
      if (stepId === "input_schema_json") {
        return { ...current, inputSchemaJson: asTextareaValue(draft.input_schema_json) };
      }
      if (stepId === "output_schema_json") {
        return { ...current, outputSchemaJson: asTextareaValue(draft.output_schema_json) };
      }
      if (stepId === "default_metric_config_json") {
        return {
          ...current,
          defaultMetricConfigJson: asTextareaValue(draft.default_metric_config_json),
        };
      }
      if (stepId === "task_definition_json") {
        return { ...current, taskDefinitionJson: asTextareaValue(draft.task_definition_json) };
      }
      return { ...current, reportProfileJson: asTextareaValue(draft.report_profile_json) };
    });
    setDraftReview((current) => {
      if (!current || current.acceptedStepIds.includes(stepId)) {
        return current;
      }
      return {
        ...current,
        acceptedStepIds: [...current.acceptedStepIds, stepId],
      };
    });
  }

  function goToNextStep() {
    moveToStep(activeStepIndex + 1);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitMessage("");
    setSubmitError("");
    try {
      const payload = buildPayload(formState);
      const saved = selectedTemplateId
        ? await api.patch<CustomTaskTemplate>(
            `/api/v1/custom-task-templates/${selectedTemplateId}`,
            payload,
          )
        : await api.post<CustomTaskTemplate>("/api/v1/custom-task-templates", payload);
      const response = await api.get<{ items: CustomTaskTemplate[] }>("/api/v1/custom-task-templates");
      setTemplates(response.items);
      setSelectedTemplateId(saved.id);
      setFormState(buildFormState(saved));
      setSubmitMessage(t("customTasks.savedMessage"));
    } catch (error) {
      setSubmitError(toErrorMessage(error));
    }
  }

  async function onDelete() {
    if (selectedTemplateId == null) {
      return;
    }
    try {
      await api.delete(`/api/v1/custom-task-templates/${selectedTemplateId}`);
      const response = await api.get<{ items: CustomTaskTemplate[] }>("/api/v1/custom-task-templates");
      setTemplates(response.items);
      if (response.items[0]) {
        loadTemplate(response.items[0]);
      } else {
        resetToNewTemplate();
      }
      setSubmitMessage(t("customTasks.deletedMessage"));
    } catch (error) {
      setSubmitError(toErrorMessage(error));
    }
  }

  async function onGenerateDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitMessage("");
    setSubmitError("");
    setIsGeneratingDraft(true);
    try {
      const response = await api.post<GeneratedCustomTaskTemplateDraft>(
        "/api/v1/custom-task-templates/generate-draft",
        { prompt: draftPrompt.trim() },
      );
      setDraftReview({ bundle: response, acceptedStepIds: [] });
      moveToStep(0);
    } catch (error) {
      setSubmitError(toErrorMessage(error));
    } finally {
      setIsGeneratingDraft(false);
    }
  }

  function renderEditor() {
    if (activeStep.id === "task_identity") {
      return (
        <div className="grid gap-3">
          <input
            value={formState.taskKey}
            onChange={(event) =>
              setFormState((current) => ({ ...current, taskKey: event.target.value }))
            }
            placeholder={t("projects.taskKeyPlaceholder")}
            className="rounded-2xl border border-stone-300 bg-white px-4 py-3"
          />
          <input
            value={formState.taskDisplayName}
            onChange={(event) =>
              setFormState((current) => ({ ...current, taskDisplayName: event.target.value }))
            }
            placeholder={t("customTasks.taskDisplayPlaceholder")}
            className="rounded-2xl border border-stone-300 bg-white px-4 py-3"
          />
          <textarea
            rows={5}
            value={formState.taskDescription}
            onChange={(event) =>
              setFormState((current) => ({ ...current, taskDescription: event.target.value }))
            }
            placeholder={t("customTasks.taskDescriptionPlaceholder")}
            className="rounded-3xl border border-stone-300 bg-white px-4 py-3"
          />
        </div>
      );
    }

    const value =
      activeStep.id === "input_schema_json"
        ? formState.inputSchemaJson
        : activeStep.id === "output_schema_json"
          ? formState.outputSchemaJson
          : activeStep.id === "default_metric_config_json"
            ? formState.defaultMetricConfigJson
            : activeStep.id === "task_definition_json"
              ? formState.taskDefinitionJson
              : formState.reportProfileJson;

    return (
      <textarea
        rows={15}
        value={value}
        onChange={(event) => updateStepJson(activeStep.id, event.target.value)}
        className="rounded-[28px] border border-stone-300 bg-stone-950 px-4 py-4 font-mono text-sm leading-6 text-stone-100"
      />
    );
  }

  const detailCards = useMemo<DetailCard[]>(() => {
    const cards: DetailCard[] = [
      {
        id: "summary",
        title: t("customTasks.detailCards.summary"),
        content: (
          <div className="rounded-[28px] border border-white/70 bg-white/90 p-5 shadow-sm">
            <p className="text-sm leading-7 text-stone-700">{activeStep.summary}</p>
          </div>
        ),
      },
      {
        id: "fields",
        title: t("customTasks.configurableFieldsTitle"),
        content: (
          <div className="rounded-[28px] border border-stone-200 bg-white p-5">
            <div className="flex flex-wrap gap-2">
              {activeStep.configurableFields.map((field) => (
                <span
                  key={field}
                  className="rounded-full bg-stone-100 px-3 py-1 text-xs font-medium text-stone-700"
                >
                  {field}
                </span>
              ))}
            </div>
          </div>
        ),
      },
      {
        id: "examples",
        title: t("customTasks.examplesTitle"),
        content: (
          <div className="rounded-[28px] border border-stone-200 bg-white p-5">
            <div className="grid gap-3">
              {activeStep.examples.map((example) => (
                <pre
                  key={example}
                  className="overflow-x-auto rounded-2xl bg-stone-950 p-3 text-xs leading-6 text-stone-100"
                >
                  {example}
                </pre>
              ))}
            </div>
          </div>
        ),
      },
      {
        id: "usage",
        title: t("customTasks.downstreamUsageTitle"),
        content: (
          <div className="rounded-[28px] border border-stone-200 bg-white p-5">
            <div className="grid gap-3">
              {activeStep.downstreamUsage.map((usage) => (
                <div
                  key={usage}
                  className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm leading-7 text-stone-700"
                >
                  {usage}
                </div>
              ))}
            </div>
          </div>
        ),
      },
    ];

    if (draftGuidanceItem) {
      cards.push({
        id: "draft",
        title: t("customTasks.aiDraftTitle"),
        content: (
          <div className="rounded-[28px] border border-teal-200 bg-teal-50/80 p-5">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-semibold text-teal-900">{draftGuidanceItem.title}</span>
              <span className="rounded-full bg-white px-3 py-1 text-xs text-teal-800">
                {t("customTasks.draftPending")}
              </span>
            </div>
            <p className="mt-3 text-sm leading-7 text-teal-950">{draftGuidanceItem.summary}</p>
            {draftGuidanceItem.notes.length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {draftGuidanceItem.notes.map((note) => (
                  <span
                    key={note}
                    className="rounded-full bg-white px-3 py-1 text-xs text-teal-900"
                  >
                    {note}
                  </span>
                ))}
              </div>
            ) : null}
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => applyDraftStep(activeStep.id)}
                className="rounded-3xl bg-teal-700 px-4 py-2 text-sm font-medium text-white"
              >
                {t("customTasks.acceptCurrentButton")}
              </button>
              <button
                type="button"
                onClick={() => {
                  applyDraftStep(activeStep.id);
                  setActiveDetailIndex((current) => Math.min(current + 1, detailCards.length - 1));
                }}
                className="rounded-3xl border border-teal-700 px-4 py-2 text-sm font-medium text-teal-800"
              >
                {t("customTasks.acceptAndNextButton")}
              </button>
            </div>
          </div>
        ),
      });
    }

    cards.push({
      id: "editor",
      title: t("customTasks.editorPaneTitle"),
      content: (
        <div className="rounded-[28px] border border-stone-200 bg-white p-5">
          {renderEditor()}
        </div>
      ),
    });

    return cards;
  }, [activeStep, draftGuidanceItem, t]);

  const activeDetailCard = detailCards[activeDetailIndex] ?? detailCards[0];

  return (
    <AppShell>
      <div className="grid gap-6 xl:grid-cols-[0.82fr_1.18fr]">
        <Panel title={t("customTasks.catalogTitle")} description={t("customTasks.catalogDescription")}>
          <div className="grid gap-3">
            <button
              type="button"
              onClick={resetToNewTemplate}
              className="rounded-3xl border border-dashed border-stone-300 bg-white px-4 py-4 text-left text-sm text-stone-700"
            >
              {t("customTasks.newTemplateButton")}
            </button>
            {templates.map((template) => (
              <button
                key={template.id}
                type="button"
                onClick={() => loadTemplate(template)}
                className={`rounded-3xl border px-4 py-4 text-left transition ${
                  selectedTemplateId === template.id
                    ? "border-teal-700 bg-teal-50"
                    : "border-stone-200 bg-white hover:border-stone-400"
                }`}
              >
                <p className="text-sm font-semibold text-stone-900">
                  {template.task_key} · {template.task_display_name}
                </p>
                <p className="mt-1 text-xs text-stone-500">
                  {template.task_description || t("customTasks.noTaskDescription")}
                </p>
              </button>
            ))}
            {!templates.length ? (
              <p className="rounded-3xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm text-stone-500">
                {t("customTasks.emptyState")}
              </p>
            ) : null}
          </div>
        </Panel>

        <div className="grid gap-6">
          <Panel title={t("customTasks.editorTitle")} description={t("customTasks.editorDescription")}>
            <form onSubmit={onGenerateDraft} className="grid gap-3">
              <h3 className="text-sm font-semibold text-stone-900">{t("customTasks.draftTitle")}</h3>
              <p className="text-sm text-stone-600">{t("customTasks.draftDescription")}</p>
              <textarea
                rows={4}
                value={draftPrompt}
                onChange={(event) => setDraftPrompt(event.target.value)}
                placeholder={t("customTasks.draftPromptPlaceholder")}
                className="rounded-3xl border border-stone-300 bg-white px-4 py-3"
              />
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="submit"
                  disabled={isGeneratingDraft || draftPrompt.trim().length < 10}
                  className="rounded-3xl bg-stone-900 px-5 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isGeneratingDraft
                    ? t("customTasks.generatingButton")
                    : t("customTasks.generateButton")}
                </button>
                <span className="text-xs text-stone-500">{t("customTasks.scrollHint")}</span>
              </div>
            </form>
          </Panel>

          <Panel title={t("customTasks.contractTitle")} description={t("customTasks.contractDescription")}>
            <div className="grid gap-5 lg:grid-cols-[220px_minmax(0,1fr)]">
              <div className="grid gap-2">
                {stepDefinitions.map((step, index) => {
                  const accepted = draftReview?.acceptedStepIds.includes(step.id) ?? false;
                  const isActive = index === activeStepIndex;
                  return (
                    <button
                      key={step.id}
                      type="button"
                      onClick={() => moveToStep(index)}
                      className={`rounded-3xl border px-4 py-4 text-left transition ${
                        isActive
                          ? "border-stone-900 bg-stone-900 text-white"
                          : "border-stone-200 bg-white text-stone-700 hover:border-stone-400"
                      }`}
                    >
                      <p className="text-xs uppercase tracking-[0.24em] opacity-70">{step.badge}</p>
                      <p className="mt-2 text-sm font-semibold">{step.title}</p>
                      <p className="mt-1 text-xs opacity-70">
                        {accepted ? t("customTasks.draftAccepted") : t("customTasks.draftPending")}
                      </p>
                    </button>
                  );
                })}
              </div>

              <form onSubmit={onSubmit} className="grid gap-4">
                <div
                  onWheel={handleWheel}
                  className="min-h-[720px] rounded-[32px] border border-stone-200 bg-gradient-to-br from-white via-stone-50 to-teal-50/40 p-5"
                >
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="text-xs uppercase tracking-[0.3em] text-stone-500">
                        {t("customTasks.stepCounter", {
                          current: activeStepIndex + 1,
                          total: stepDefinitions.length,
                        })}
                      </p>
                      <h3 className="mt-2 text-2xl font-semibold text-stone-900">{activeStep.title}</h3>
                      <p className="mt-2 text-sm text-stone-500">
                        {t("customTasks.detailCounter", {
                          current: activeDetailIndex + 1,
                          total: detailCards.length,
                        })}
                      </p>
                    </div>
                    <div className="rounded-full bg-white px-4 py-2 text-xs text-stone-500 shadow-sm">
                      {t("customTasks.scrollHint")}
                    </div>
                  </div>

                  <div className="mt-5 grid gap-4">
                    <div className="flex flex-wrap items-center gap-2">
                      {detailCards.map((card, index) => (
                        <button
                          key={card.id}
                          type="button"
                          onClick={() => setActiveDetailIndex(index)}
                          className={`rounded-full px-3 py-1 text-xs transition ${
                            index === activeDetailIndex
                              ? "bg-stone-900 text-white"
                              : "bg-white text-stone-600"
                          }`}
                        >
                          {card.title}
                        </button>
                      ))}
                    </div>
                    <div className="min-h-[520px]">
                      {activeDetailCard ? activeDetailCard.content : null}
                    </div>
                    <div className="flex flex-wrap gap-3">
                      <button
                        type="button"
                        onClick={() => setActiveDetailIndex((current) => Math.max(0, current - 1))}
                        disabled={activeDetailIndex === 0}
                        className="rounded-3xl border border-stone-300 px-4 py-2 text-sm text-stone-700 disabled:opacity-50"
                      >
                        {t("customTasks.prevDetailButton")}
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          setActiveDetailIndex((current) =>
                            Math.min(detailCards.length - 1, current + 1),
                          )
                        }
                        disabled={activeDetailIndex === detailCards.length - 1}
                        className="rounded-3xl border border-stone-300 px-4 py-2 text-sm text-stone-700 disabled:opacity-50"
                      >
                        {t("customTasks.nextDetailButton")}
                      </button>
                      <button
                        type="button"
                        onClick={goToNextStep}
                        className="rounded-3xl border border-teal-700 px-4 py-2 text-sm font-medium text-teal-800"
                      >
                        {t("customTasks.skipCurrentButton")}
                      </button>
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap gap-3">
                  <button
                    type="submit"
                    className="rounded-3xl bg-teal-700 px-5 py-3 text-sm font-medium text-white"
                  >
                    {t("customTasks.saveButton")}
                  </button>
                  <button
                    type="button"
                    onClick={onDelete}
                    disabled={selectedTemplateId == null}
                    className="rounded-3xl border border-stone-300 px-5 py-3 text-sm font-medium text-stone-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {t("customTasks.deleteButton")}
                  </button>
                </div>
              </form>
            </div>
          </Panel>

          {submitMessage ? <p className="text-sm text-emerald-700">{submitMessage}</p> : null}
          {submitError ? <p className="text-sm text-rose-700">{submitError}</p> : null}

          <Panel title={t("customTasks.previewTitle")} description={t("customTasks.previewDescription")}>
            <JsonView
              value={buildLivePreview(formState)}
              emptyLabel={t("customTasks.previewEmpty")}
            />
          </Panel>
        </div>
      </div>
    </AppShell>
  );
}
