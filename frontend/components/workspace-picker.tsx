import { Dataset, Project, PromptRecord } from "@/lib/studio";
import { useI18n } from "@/lib/i18n/provider";

type WorkspacePickerProps = {
  projects: Project[];
  datasets: Dataset[];
  prompts: PromptRecord[];
  selectedProjectId: number | null;
  selectedDatasetId?: number | null;
  selectedPromptId?: number | null;
  onProjectChange: (value: number | null) => void;
  onDatasetChange?: (value: number | null) => void;
  onPromptChange?: (value: number | null) => void;
};

export function WorkspacePicker({
  projects,
  datasets,
  prompts,
  selectedProjectId,
  selectedDatasetId,
  selectedPromptId,
  onProjectChange,
  onDatasetChange,
  onPromptChange,
}: WorkspacePickerProps) {
  const { t } = useI18n();
  const filteredDatasets = selectedProjectId
    ? datasets.filter((item) => item.project_id === selectedProjectId)
    : [];
  const filteredPrompts = selectedProjectId
    ? prompts.filter((item) => item.project_id === selectedProjectId)
    : [];

  return (
    <div className="grid gap-4 md:grid-cols-3">
      <label className="grid gap-2 text-sm">
        <span className="font-medium text-stone-700">{t("common.workspace.project")}</span>
        <select
          value={selectedProjectId ?? ""}
          onChange={(event) => onProjectChange(event.target.value ? Number(event.target.value) : null)}
          className="rounded-2xl border border-stone-300 bg-white px-4 py-3"
        >
          <option value="">{t("common.workspace.selectProject")}</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              #{project.id} · {project.name}
            </option>
          ))}
        </select>
      </label>

      {onDatasetChange ? (
        <label className="grid gap-2 text-sm">
          <span className="font-medium text-stone-700">{t("common.workspace.dataset")}</span>
          <select
            value={selectedDatasetId ?? ""}
            onChange={(event) => onDatasetChange(event.target.value ? Number(event.target.value) : null)}
            className="rounded-2xl border border-stone-300 bg-white px-4 py-3"
          >
            <option value="">{t("common.workspace.selectDataset")}</option>
            {filteredDatasets.map((dataset) => (
              <option key={dataset.id} value={dataset.id}>
                #{dataset.id} · {dataset.name}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {onPromptChange ? (
        <label className="grid gap-2 text-sm">
          <span className="font-medium text-stone-700">{t("common.workspace.prompt")}</span>
          <select
            value={selectedPromptId ?? ""}
            onChange={(event) => onPromptChange(event.target.value ? Number(event.target.value) : null)}
            className="rounded-2xl border border-stone-300 bg-white px-4 py-3"
          >
            <option value="">{t("common.workspace.selectPrompt")}</option>
            {filteredPrompts.map((prompt) => (
              <option key={prompt.id} value={prompt.id}>
                #{prompt.id} · {prompt.name} v{prompt.version}
              </option>
            ))}
          </select>
        </label>
      ) : null}
    </div>
  );
}
