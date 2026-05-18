"""全局常量定义模块。

定义项目中各类实体（项目、提示词、数据集等）的状态集合与枚举常量，
供其他模块统一引用以确保一致性。
"""

BUILTIN_TASK_KEYS = {
    "qa",
    "json_generation",
    "rate",
}

PROJECT_STATUSES = {"active", "archived"}
PROMPT_STATUSES = {"draft", "active", "archived"}
DATASET_STATUSES = {"active", "archived"}
DATASET_SOURCE_TYPES = {"manual_upload", "synthetic_generated", "edited", "imported"}
DATASET_SPLITS = {"train", "dev", "test", "unassigned"}
ARTIFACT_OWNER_TYPES = {"dataset", "evaluation", "optimization_run"}
FEEDBACK_RICH_METRICS = {"gepa_feedback_metric"}
