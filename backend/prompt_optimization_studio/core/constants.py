BUILTIN_TASK_KEYS = {
    "classification",
    "extraction",
    "qa",
    "json_generation",
    "rewriting",
    "rate",
}

PROJECT_STATUSES = {"active", "archived"}
PROMPT_STATUSES = {"draft", "active", "archived"}
DATASET_STATUSES = {"active", "archived"}
DATASET_SOURCE_TYPES = {"manual_upload", "synthetic_generated", "edited", "imported"}
DATASET_SPLITS = {"train", "dev", "test", "unassigned"}
QUALITY_STATUSES = {"unchecked", "accepted", "rejected", "needs_review"}
ARTIFACT_OWNER_TYPES = {"dataset", "evaluation", "optimization_run"}
FEEDBACK_RICH_METRICS = {"gepa_feedback_metric"}
