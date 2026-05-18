from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "Prompt Optimization Studio"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    data_dir: Path = Path("data")
    database_url: str = "sqlite:///data/app.db"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_default_model: str = "deepseek-v4-pro"

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
        return self.data_dir / "uploads"

    @computed_field
    @property
    def artifacts_dir(self) -> Path:
        return self.data_dir / "artifacts"

    @computed_field
    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "reports"

    @computed_field
    @property
    def generated_dir(self) -> Path:
        return self.data_dir / "generated"


@lru_cache
def get_settings() -> Settings:
    return Settings()
