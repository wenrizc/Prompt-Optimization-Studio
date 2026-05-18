from pathlib import Path

from prompt_optimization_studio.core.config import get_settings


def ensure_runtime_directories() -> None:
    settings = get_settings()
    directories: list[Path] = [
        settings.data_dir,
        settings.uploads_dir,
        settings.artifacts_dir,
        settings.reports_dir,
        settings.generated_dir,
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
