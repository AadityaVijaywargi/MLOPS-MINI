"""Runtime configuration. Every environment-specific value is injected through
environment variables (see .env.example); nothing here names a provider,
endpoint, credential or LLM model."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    service_name: str = "bpc"
    log_level: str = "INFO"

    # Infrastructure
    redis_url: str = "redis://redis:6379/0"
    db_host: str = "postgres"
    db_port: int = 5432
    db_name: str = "bpc"
    db_user: str = "bpc"
    db_password: str | None = None
    db_password_file: str | None = None
    retriever_url: str = "http://retriever:8001"
    llm_gateway_url: str = "http://llm-gateway:8002"
    otel_exporter_otlp_endpoint: str | None = None
    jaeger_ui_url: str = "http://localhost:16686"

    # Paths inside containers
    prompts_dir: str = "/app/prompts"
    corpus_dir: str = "/corpus"
    index_dir: str = "/index"

    # Retrieval
    embedding_model: str | None = None
    retrieval_cache_ttl_s: int = 3600
    retrieval_cache_enabled: bool = True

    # Agent loop bounds (A1)
    researcher_max_steps: int = 14
    researcher_max_tool_calls: int = 24
    researcher_deadline_s: float = 120.0
    assessor_max_verification_retries: int = 1
    assessor_max_research_handbacks: int = 1
    assessor_deadline_s: float = 90.0
    tool_timeout_s: float = 10.0
    tool_max_retries: int = 2
    llm_client_timeout_s: float = 75.0
    worker_concurrency: int = 4
    job_lease_s: int = 60
    job_max_attempts: int = 2
    run_deadline_s: float = 300.0

    # API
    rate_limit_per_minute: int = 20
    rate_limit_overrides: str = ""  # "clientA:100,eval:300"
    run_cache_enabled: bool = True
    run_cache_ttl_s: int = 86400
    online_eval_sample_rate: float = 0.25

    # Prompt variants (L2)
    prompt_variant_assessor: str = "v2"
    modifier_search_enabled: bool = True
    context_compaction_enabled: bool = True

    @property
    def database_dsn(self) -> str:
        password = self.db_password
        if not password and self.db_password_file and Path(self.db_password_file).exists():
            password = Path(self.db_password_file).read_text().strip()
        auth = self.db_user if not password else f"{self.db_user}:{password}"
        return f"postgresql://{auth}@{self.db_host}:{self.db_port}/{self.db_name}"

    def rate_limit_for(self, client_id: str) -> int:
        for item in filter(None, (p.strip() for p in self.rate_limit_overrides.split(","))):
            name, _, limit = item.partition(":")
            if name == client_id and limit.isdigit():
                return int(limit)
        return self.rate_limit_per_minute


@lru_cache
def get_settings() -> Settings:
    return Settings()
