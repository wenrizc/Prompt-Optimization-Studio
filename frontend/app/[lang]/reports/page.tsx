"use client";

import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { JsonView } from "@/components/json-view";
import { Panel } from "@/components/panel";
import { StatusChip } from "@/components/status-chip";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { EvaluationRecord, OptimizationRunRecord, formatScore, toErrorMessage } from "@/lib/studio";

type ArtifactManifest = {
  owner_type: string;
  owner_id: number;
  artifacts: Array<{
    artifact_type: string;
    relative_path: string;
    metadata_json: {
      file_name?: string;
      size_bytes?: number;
      sha256?: string;
    };
  }>;
};

type ArtifactItem = {
  id: number;
  owner_type: string;
  owner_id: number;
  artifact_type: string;
  relative_path: string;
  metadata_json: Record<string, unknown>;
};

type DerivedPromptCandidateArtifact = {
  system_prompt?: string;
  user_template?: string;
  notes?: string;
};

type DerivedPromptDiffArtifact = {
  before_system_prompt?: string;
  after_system_prompt?: string;
  before_user_template?: string;
  after_user_template?: string;
};

type ArtifactSection = {
  title: string;
  description: string;
  items: ArtifactItem[];
};

function SummaryCard({
  title,
  value,
  hint,
}: {
  title: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-[24px] border border-stone-900/10 bg-white p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-stone-500">{title}</p>
      <p className="mt-2 text-2xl font-semibold text-stone-900">{value}</p>
      <p className="mt-2 text-sm text-stone-500">{hint}</p>
    </div>
  );
}

export default function ReportsPage() {
  const { t } = useI18n();
  const [mode, setMode] = useState<"evaluation" | "optimization">("evaluation");
  const [evaluations, setEvaluations] = useState<EvaluationRecord[]>([]);
  const [runs, setRuns] = useState<OptimizationRunRecord[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [manifest, setManifest] = useState<ArtifactManifest | null>(null);
  const [artifactItems, setArtifactItems] = useState<ArtifactItem[]>([]);
  const [selectedArtifactId, setSelectedArtifactId] = useState<number | null>(null);
  const [selectedArtifactContent, setSelectedArtifactContent] = useState<unknown>(null);
  const [derivedPromptCandidate, setDerivedPromptCandidate] = useState<DerivedPromptCandidateArtifact | null>(null);
  const [derivedPromptDiff, setDerivedPromptDiff] = useState<DerivedPromptDiffArtifact | null>(null);
  const [error, setError] = useState("");
  const isEvaluationMode = mode === "evaluation";

  useEffect(() => {
    void Promise.all([
      api.get<{ items: EvaluationRecord[] }>("/api/v1/evaluations").then((result) => setEvaluations(result.items)),
      api.get<{ items: OptimizationRunRecord[] }>("/api/v1/optimization-runs").then((result) => setRuns(result.items)),
    ]).catch((loadError) => setError(toErrorMessage(loadError)));
  }, []);

  const items = useMemo(
    () => (mode === "evaluation" ? evaluations : runs),
    [mode, evaluations, runs],
  );

  const summary = (report?.summary ?? {}) as Record<string, unknown>;
  const warnings = Array.isArray(report?.warnings) ? (report?.warnings as unknown[]) : [];
  const failedExamples = Array.isArray(report?.failed_examples) ? (report?.failed_examples as unknown[]) : [];
  const regressionExamples = Array.isArray(report?.regression_examples)
    ? (report?.regression_examples as unknown[])
    : [];
  const executiveSummary =
    typeof report?.executive_summary === "string" ? report.executive_summary : "";

  async function loadReport(nextMode: "evaluation" | "optimization", id: number) {
    setError("");
    setSelectedArtifactId(null);
    setSelectedArtifactContent(null);
    setDerivedPromptCandidate(null);
    setDerivedPromptDiff(null);
    try {
      const path = nextMode === "evaluation" ? `/api/v1/evaluations/${id}/report` : `/api/v1/optimization-runs/${id}/report`;
      const ownerType = nextMode === "evaluation" ? "evaluation" : "optimization_run";
      const [payload, ownerManifest, ownerArtifacts] = await Promise.all([
        api.get<Record<string, unknown>>(path),
        api.get<ArtifactManifest>(`/api/v1/artifacts/${ownerType}/${id}/manifest`),
        api.get<{ items: ArtifactItem[] }>(`/api/v1/artifacts/${ownerType}/${id}`),
      ]);
      setSelectedId(id);
      setReport(payload);
      setManifest(ownerManifest);
      setArtifactItems(ownerArtifacts.items);
      if (nextMode === "optimization") {
        const derivedPromptArtifact = ownerArtifacts.items.find((item) => item.artifact_type === "derived_prompt_candidate");
        const promptDiffArtifact = ownerArtifacts.items.find((item) => item.artifact_type === "derived_prompt_diff");
        const [derivedPromptPayload, promptDiffPayload] = await Promise.all([
          derivedPromptArtifact
            ? api.get<{ artifact: ArtifactItem; content: DerivedPromptCandidateArtifact }>(`/api/v1/artifacts/item/${derivedPromptArtifact.id}`)
            : Promise.resolve(null),
          promptDiffArtifact
            ? api.get<{ artifact: ArtifactItem; content: DerivedPromptDiffArtifact }>(`/api/v1/artifacts/item/${promptDiffArtifact.id}`)
            : Promise.resolve(null),
        ]);
        setDerivedPromptCandidate(derivedPromptPayload?.content ?? null);
        setDerivedPromptDiff(promptDiffPayload?.content ?? null);
      }
    } catch (loadError) {
      setError(toErrorMessage(loadError));
    }
  }

  async function loadArtifactContent(artifactId: number) {
    setError("");
    try {
      const payload = await api.get<{ artifact: ArtifactItem; content: unknown }>(
        `/api/v1/artifacts/item/${artifactId}`,
      );
      setSelectedArtifactId(artifactId);
      setSelectedArtifactContent(payload.content);
    } catch (loadError) {
      setError(toErrorMessage(loadError));
    }
  }

  const hasOptimizationPromptCard =
    mode === "optimization" && (derivedPromptCandidate != null || derivedPromptDiff != null);
  const artifactSections = useMemo<ArtifactSection[]>(() => {
    const coreTypes = new Set(["report", "baseline_predictions", "optimized_predictions", "comparative_results", "predictions"]);
    if (isEvaluationMode) {
      return [
        {
          title: t("reports.evaluationArtifactsTitle"),
          description: t("reports.evaluationArtifactsDescription"),
          items: artifactItems.filter((item) => coreTypes.has(item.artifact_type)),
        },
      ];
    }

    return [
      {
        title: t("reports.optimizationCoreArtifactsTitle"),
        description: t("reports.optimizationCoreArtifactsDescription"),
        items: artifactItems.filter((item) => coreTypes.has(item.artifact_type)),
      },
      {
        title: t("reports.optimizationPromptArtifactsTitle"),
        description: t("reports.optimizationPromptArtifactsDescription"),
        items: artifactItems.filter((item) =>
          ["derived_prompt_candidate", "derived_prompt_diff"].includes(item.artifact_type),
        ),
      },
      {
        title: t("reports.optimizationDebugArtifactsTitle"),
        description: t("reports.optimizationDebugArtifactsDescription"),
        items: artifactItems.filter((item) =>
          ["compiled_program", "fewshot_demos"].includes(item.artifact_type),
        ),
      },
    ].filter((section) => section.items.length > 0);
  }, [artifactItems, isEvaluationMode, t]);

  return (
    <AppShell>
      <Panel title={t("reports.title")} description={t("reports.description")}>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => {
              setMode("evaluation");
              setSelectedId(null);
              setReport(null);
              setManifest(null);
              setArtifactItems([]);
              setDerivedPromptCandidate(null);
              setDerivedPromptDiff(null);
            }}
            className={`rounded-3xl px-5 py-3 text-sm font-medium ${
              mode === "evaluation" ? "bg-stone-900 text-white" : "border border-stone-300 bg-white text-stone-800"
            }`}
            type="button"
          >
            {t("reports.evaluationTab")}
          </button>
          <button
            onClick={() => {
              setMode("optimization");
              setSelectedId(null);
              setReport(null);
              setManifest(null);
              setArtifactItems([]);
              setDerivedPromptCandidate(null);
              setDerivedPromptDiff(null);
            }}
            className={`rounded-3xl px-5 py-3 text-sm font-medium ${
              mode === "optimization" ? "bg-stone-900 text-white" : "border border-stone-300 bg-white text-stone-800"
            }`}
            type="button"
          >
            {t("reports.optimizationTab")}
          </button>
        </div>
      </Panel>

      <div className="grid gap-6 xl:grid-cols-[0.86fr_1.14fr]">
        <Panel title={t("reports.availableTitle")} description={t("reports.availableDescription")}>
          <div className="grid gap-3">
            {items.map((item) => (
              <button
                key={item.id}
                onClick={() => void loadReport(mode, item.id)}
                type="button"
                className={`rounded-3xl border px-4 py-4 text-left ${
                  selectedId === item.id ? "border-stone-900 bg-stone-100" : "border-stone-200 bg-white"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-stone-900">
                      {"optimizer_name" in item
                        ? t("reports.reportItemTitleOptimization", {
                            id: item.id,
                            optimizer: item.optimizer_name,
                          })
                        : t("reports.reportItemTitleEvaluation", {
                            id: item.id,
                            datasetId: item.dataset_id,
                          })}
                    </p>
                    <p className="mt-1 text-xs text-stone-500">
                      {t("reports.projectPrompt", {
                        projectId: item.project_id,
                        promptId: item.prompt_id,
                      })}
                    </p>
                  </div>
                  <StatusChip value={item.status} />
                </div>
              </button>
            ))}
          </div>
          {error ? <p className="mt-4 text-sm text-rose-700">{error}</p> : null}
        </Panel>

        <div className="grid gap-6">
          <Panel title={t("reports.executiveTitle")} description={t("reports.executiveDescription")}>
            {report ? (
              <div className="space-y-4">
                <div className="grid gap-4 md:grid-cols-3">
                  {isEvaluationMode ? (
                    <>
                      <SummaryCard
                        title={t("reports.evaluationScoreCard")}
                        value={formatScore(typeof summary.baseline_score === "number" ? summary.baseline_score : null)}
                        hint={t("reports.evaluationScoreHint")}
                      />
                      <SummaryCard
                        title={t("reports.evaluationExamplesCard")}
                        value={String(typeof summary.evaluated_examples === "number" ? summary.evaluated_examples : "—")}
                        hint={t("reports.evaluationExamplesHint")}
                      />
                      <SummaryCard
                        title={t("reports.evaluationMetricCard")}
                        value={typeof summary.metric === "string" ? summary.metric : "—"}
                        hint={t("reports.evaluationMetricHint")}
                      />
                    </>
                  ) : (
                    <>
                      <SummaryCard
                        title={t("reports.baselineCard")}
                        value={formatScore(typeof summary.baseline_score === "number" ? summary.baseline_score : null)}
                        hint={t("reports.baselineHint")}
                      />
                      <SummaryCard
                        title={t("reports.optimizedCard")}
                        value={formatScore(typeof summary.optimized_score === "number" ? summary.optimized_score : null)}
                        hint={t("reports.optimizedHint")}
                      />
                      <SummaryCard
                        title={t("reports.deltaCard")}
                        value={formatScore(typeof summary.delta === "number" ? summary.delta : null)}
                        hint={t("reports.deltaHint")}
                      />
                    </>
                  )}
                </div>
                <div className="rounded-[24px] border border-stone-900/10 bg-white p-5">
                  <p className="text-sm leading-7 text-stone-700 whitespace-pre-wrap">
                    {executiveSummary || t("reports.noExecutiveSummary")}
                  </p>
                </div>
              </div>
            ) : (
              <JsonView value={null} emptyLabel={t("reports.selectSummaryEmpty")} />
            )}
          </Panel>

          <Panel title={t("reports.warningsTitle")} description={t("reports.warningsDescription")}>
            <div className="grid gap-4 xl:grid-cols-3">
              <div>
                <h3 className="mb-2 text-sm font-semibold text-stone-900">{t("reports.warnings")}</h3>
                <JsonView value={warnings} emptyLabel={t("reports.warningsEmpty")} />
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold text-stone-900">{t("reports.failedExamples")}</h3>
                <JsonView value={failedExamples} emptyLabel={t("reports.failedExamplesEmpty")} />
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold text-stone-900">{t("reports.regressionExamples")}</h3>
                <JsonView
                  value={isEvaluationMode ? null : regressionExamples}
                  emptyLabel={
                    isEvaluationMode
                      ? t("reports.regressionExamplesNotApplicable")
                      : t("reports.regressionExamplesEmpty")
                  }
                />
              </div>
            </div>
          </Panel>

          {hasOptimizationPromptCard ? (
            <Panel title={t("reports.optimizedPromptTitle")} description={t("reports.optimizedPromptDescription")}>
              <div className="grid gap-4">
                <div className="rounded-[24px] border border-stone-900/10 bg-white p-5">
                  <h3 className="text-sm font-semibold text-stone-900">{t("reports.optimizedSystemPrompt")}</h3>
                  <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded-3xl bg-stone-950 p-4 text-xs leading-6 text-stone-100">
                    {derivedPromptCandidate?.system_prompt || t("reports.optimizedPromptEmpty")}
                  </pre>
                </div>
                <div className="rounded-[24px] border border-stone-900/10 bg-white p-5">
                  <h3 className="text-sm font-semibold text-stone-900">{t("reports.optimizedUserTemplate")}</h3>
                  <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded-3xl bg-stone-950 p-4 text-xs leading-6 text-stone-100">
                    {derivedPromptCandidate?.user_template || t("reports.optimizedPromptEmpty")}
                  </pre>
                </div>
                {derivedPromptCandidate?.notes ? (
                  <div className="rounded-[24px] border border-amber-200 bg-amber-50 p-5 text-sm text-amber-950">
                    {derivedPromptCandidate.notes}
                  </div>
                ) : null}
                <div className="grid gap-4 xl:grid-cols-2">
                  <div className="rounded-[24px] border border-stone-900/10 bg-white p-5">
                    <h3 className="text-sm font-semibold text-stone-900">{t("reports.promptDiffSystem")}</h3>
                    <JsonView
                      value={
                        derivedPromptDiff
                          ? {
                              before: derivedPromptDiff.before_system_prompt,
                              after: derivedPromptDiff.after_system_prompt,
                            }
                          : null
                      }
                      emptyLabel={t("reports.optimizedPromptEmpty")}
                    />
                  </div>
                  <div className="rounded-[24px] border border-stone-900/10 bg-white p-5">
                    <h3 className="text-sm font-semibold text-stone-900">{t("reports.promptDiffUserTemplate")}</h3>
                    <JsonView
                      value={
                        derivedPromptDiff
                          ? {
                              before: derivedPromptDiff.before_user_template,
                              after: derivedPromptDiff.after_user_template,
                            }
                          : null
                      }
                      emptyLabel={t("reports.optimizedPromptEmpty")}
                    />
                  </div>
                </div>
              </div>
            </Panel>
          ) : null}

          <Panel title={t("reports.artifactsTitle")} description={t("reports.artifactsDescription")}>
            {manifest ? (
              <div className="space-y-4">
                {artifactSections.map((section) => (
                  <div key={section.title} className="rounded-[24px] border border-stone-200 bg-white p-4">
                    <div className="mb-4">
                      <h3 className="text-sm font-semibold text-stone-900">{section.title}</h3>
                      <p className="mt-1 text-xs text-stone-500">{section.description}</p>
                    </div>
                    <div className="grid gap-3">
                      {section.items.map((artifact) => (
                        <div key={artifact.id} className="rounded-[24px] border border-stone-200 bg-stone-50 p-4">
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                              <p className="text-sm font-semibold text-stone-900">
                                {artifact.artifact_type}
                              </p>
                              <p className="mt-1 text-xs text-stone-500">
                                {String(artifact.metadata_json.file_name ?? artifact.relative_path)}
                              </p>
                            </div>
                            <div className="flex flex-wrap gap-2">
                              <button
                                onClick={() => void loadArtifactContent(artifact.id)}
                                type="button"
                                className="rounded-full border border-stone-300 bg-white px-4 py-2 text-sm font-medium text-stone-800"
                              >
                                {t("reports.previewButton")}
                              </button>
                              <a
                                href={api.url(`/api/v1/artifacts/item/${artifact.id}/download`)}
                                target="_blank"
                                rel="noreferrer"
                                className="rounded-full bg-stone-900 px-4 py-2 text-sm font-medium text-white"
                              >
                                {t("reports.openFileButton")}
                              </a>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}

                <div className="rounded-[24px] border border-stone-200 bg-white p-4">
                  <h3 className="mb-2 text-sm font-semibold text-stone-900">
                    {selectedArtifactId
                      ? t("reports.artifactPreviewWithId", { id: selectedArtifactId })
                      : t("reports.artifactPreview")}
                  </h3>
                  <JsonView value={selectedArtifactContent} emptyLabel={t("reports.artifactPreviewEmpty")} />
                </div>

                <details className="rounded-[24px] border border-stone-200 bg-white p-4">
                  <summary className="cursor-pointer list-none text-sm font-semibold text-stone-900">
                    {t("reports.advancedArtifactsToggle")}
                  </summary>
                  <div className="mt-4">
                    <h3 className="mb-2 text-sm font-semibold text-stone-900">{t("reports.manifest")}</h3>
                    <JsonView value={manifest} emptyLabel={t("reports.manifestEmpty")} />
                  </div>
                </details>
              </div>
            ) : (
              <JsonView value={null} emptyLabel={t("reports.selectArtifactsEmpty")} />
            )}
          </Panel>
        </div>
      </div>
    </AppShell>
  );
}
