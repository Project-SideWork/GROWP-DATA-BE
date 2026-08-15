from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "analysis-pipeline"
    app_env: str = "local"
    log_level: str = "INFO"
    backend_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8080")
    backend_result_path: str = "/api/v1/analysis-results"
    backend_project_applicants_path: str = "/api/v1/analytics/projects/{id}/evaluation-dataset"
    backend_club_applicants_path: str = "/api/v1/analytics/clubs/{id}/applicants"
    backend_study_applicants_path: str = "/api/v1/analytics/studies/{id}/evaluation-dataset"
    backend_api_key: str = ""
    request_timeout_seconds: float = Field(default=10, gt=0)
    delivery_max_attempts: int = Field(default=3, ge=1, le=10)
    backend_fetch_concurrency: int = Field(default=5, ge=1, le=50)
    kafka_enabled: bool = False
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_client_id: str = "growp-analysis-pipeline"
    kafka_consumer_group_id: str = "growp-analysis-consumer"


@lru_cache
def get_settings() -> Settings:
    return Settings()
