"""应用配置模块。

基于 pydantic-settings 从环境变量和 .env 文件加载全局配置，包括服务端口、
数据目录、OpenAI 接口参数以及各类运行时限制。
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局应用配置项。

    通过 .env 文件或环境变量进行配置，涵盖服务绑定、数据存储路径、
    LLM 接入参数及资源使用上限。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    host: str = "127.0.0.1"
    port: int = 8000
    app_name: str = "Prompt Optimization Studio"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    data_dir: Path = Path("data")
    database_url: str = "sqlite:///data/app.db"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_default_model: str = "deepseek-v4-pro"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    static_dir: Path | None = None

    max_upload_size_mb: int = Field(default=25, ge=1)
    max_artifact_size_mb: int = Field(default=250, ge=1)
    max_generated_examples: int = Field(default=500, ge=1)
    max_examples_per_run: int = Field(default=1000, ge=1)
    max_optimizer_threads: int = Field(default=4, ge=1)
    max_lm_calls: int = Field(default=5000, ge=1)
    max_metric_calls: int = Field(default=5000, ge=1)
    max_runtime_seconds: int = Field(default=7200, ge=60)

    @computed_field
    @property
    def uploads_dir(self) -> Path:
        """用户上传文件的存储目录。"""
        return self.data_dir / "uploads"

    @computed_field
    @property
    def artifacts_dir(self) -> Path:
        """制品（如优化后的提示词）的存储目录。"""
        return self.data_dir / "artifacts"

    @computed_field
    @property
    def reports_dir(self) -> Path:
        """评估报告的存储目录。"""
        return self.data_dir / "reports"

    @computed_field
    @property
    def generated_dir(self) -> Path:
        """合成生成数据的存储目录。"""
        return self.data_dir / "generated"


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例。

    Returns:
        缓存的 Settings 实例。
    """
    return Settings()
