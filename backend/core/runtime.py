"""运行时环境初始化模块。

在应用启动时确保所需的数据目录结构已就绪。
"""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

from backend.core.config import get_settings


def ensure_runtime_directories() -> None:
    """确保所有运行时数据目录存在，不存在则自动创建。"""
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
