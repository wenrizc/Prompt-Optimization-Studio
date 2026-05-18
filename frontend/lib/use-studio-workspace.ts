"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { Dataset, Project, PromptRecord, toErrorMessage } from "@/lib/studio";

const PROJECT_KEY = "studio:selected-project-id";
const DATASET_KEY = "studio:selected-dataset-id";
const PROMPT_KEY = "studio:selected-prompt-id";

export function useStudioWorkspace() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [prompts, setPrompts] = useState<PromptRecord[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [selectedDatasetId, setSelectedDatasetId] = useState<number | null>(null);
  const [selectedPromptId, setSelectedPromptId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const projectId = window.localStorage.getItem(PROJECT_KEY);
    const datasetId = window.localStorage.getItem(DATASET_KEY);
    const promptId = window.localStorage.getItem(PROMPT_KEY);
    setSelectedProjectId(projectId ? Number(projectId) : null);
    setSelectedDatasetId(datasetId ? Number(datasetId) : null);
    setSelectedPromptId(promptId ? Number(promptId) : null);
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined") {
      if (selectedProjectId) {
        window.localStorage.setItem(PROJECT_KEY, String(selectedProjectId));
      } else {
        window.localStorage.removeItem(PROJECT_KEY);
      }
    }
  }, [selectedProjectId]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      if (selectedDatasetId) {
        window.localStorage.setItem(DATASET_KEY, String(selectedDatasetId));
      } else {
        window.localStorage.removeItem(DATASET_KEY);
      }
    }
  }, [selectedDatasetId]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      if (selectedPromptId) {
        window.localStorage.setItem(PROMPT_KEY, String(selectedPromptId));
      } else {
        window.localStorage.removeItem(PROMPT_KEY);
      }
    }
  }, [selectedPromptId]);

  async function refreshWorkspace() {
    setLoading(true);
    setError("");
    try {
      const [projectsResponse, datasetsResponse, promptsResponse] = await Promise.all([
        api.get<{ items: Project[] }>("/api/v1/projects"),
        api.get<{ items: Dataset[] }>("/api/v1/datasets"),
        api.get<{ items: PromptRecord[] }>("/api/v1/prompts"),
      ]);
      setProjects(projectsResponse.items);
      setDatasets(datasetsResponse.items);
      setPrompts(promptsResponse.items);
    } catch (refreshError) {
      setError(toErrorMessage(refreshError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshWorkspace();
  }, []);

  return {
    projects,
    datasets,
    prompts,
    selectedProjectId,
    selectedDatasetId,
    selectedPromptId,
    setSelectedProjectId,
    setSelectedDatasetId,
    setSelectedPromptId,
    loading,
    error,
    refreshWorkspace,
  };
}
