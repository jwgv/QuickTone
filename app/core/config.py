from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Environment variables are prefixed with QT_. For example, QT_PORT, QT_HOST, etc.
    Defaults are performance-oriented for local development.
    """

    # Core
    ENV: str = Field(default="dev", alias="QT_ENV")
    PORT: int = Field(default=8080, alias="QT_PORT")
    HOST: str = Field(default="0.0.0.0", alias="QT_HOST")
    MODEL_DEFAULT: str = Field(default="vader", alias="QT_MODEL_DEFAULT")  # vader|distilbert

    # Auth
    AUTH_MODE: str = Field(default="none", alias="QT_AUTH_MODE")  # none|api_key
    API_KEYS: str = Field(default="", alias="QT_API_KEYS")  # comma-separated

    # Performance & limits
    RATE_LIMIT_ENABLED: bool = Field(default=False, alias="QT_RATE_LIMIT_ENABLED")
    RATE_LIMIT_RPS: int = Field(default=10, alias="QT_RATE_LIMIT_RPS")
    RESPONSE_TIMEOUT_MS: int = Field(default=500, alias="QT_RESPONSE_TIMEOUT_MS")
    BATCH_SIZE_LIMIT: int = Field(default=32, alias="QT_BATCH_SIZE_LIMIT")
    TEXT_LENGTH_LIMIT: int = Field(default=2500, alias="QT_TEXT_LENGTH_LIMIT")

    # Caching
    CACHE_BACKEND: str = Field(default="none", alias="QT_CACHE_BACKEND")  # none|memory
    CACHE_TTL_SECONDS: int = Field(default=3600, alias="QT_CACHE_TTL_SECONDS")

    # Models
    MODEL_WARM_ON_STARTUP: bool = Field(default=True, alias="QT_MODEL_WARM_ON_STARTUP")
    DISTILBERT_MODEL: str = Field(
        default="joeddav/distilbert-base-uncased-go-emotions-student",
        alias="QT_DISTILBERT_MODEL",
    )
    EMOTION_MODEL: str = Field(
        default="joeddav/distilbert-base-uncased-go-emotions-student",
        alias="QT_EMOTION_MODEL",
    )
    DISTILBERT_SST_2_MODEL: str = Field(
        default="distilbert-base-uncased-finetuned-sst-2-english",
        alias="QT_DISTILBERT_SST_2_MODEL",
    )
    GRACEFUL_DEGRADATION: bool = Field(default=True, alias="QT_GRACEFUL_DEGRADATION")
    USE_ONNX_RUNTIME: bool = Field(default=False, alias="QT_USE_ONNX_RUNTIME")

    # Logging & observability
    LOG_LEVEL: str = Field(default="info", alias="QT_LOG_LEVEL")
    PERFORMANCE_LOGGING: bool = Field(default=True, alias="QT_PERFORMANCE_LOGGING")

    # Performance targets (for tests/benchmarks)
    PERF_VADER_MAX_MS: int = Field(default=50, alias="QT_PERF_VADER_MAX_MS")
    PERF_DISTILBERT_MAX_MS: int = Field(default=300, alias="QT_PERF_DISTILBERT_MAX_MS")
    PERF_BATCH_MAX_MS_PER_ITEM: int = Field(default=100, alias="QT_PERF_BATCH_MAX_MS_PER_ITEM")

    # Emotion→sentiment mapping knobs
    EMO_SENT_THRESHOLD: float = Field(default=0.35, alias="QT_EMO_SENT_THRESHOLD")
    EMO_SENT_EPSILON: float = Field(default=0.05, alias="QT_EMO_SENT_EPSILON")

    # Optional integrations (stubs)
    ENABLE_MCP: bool = Field(default=False, alias="QT_ENABLE_MCP")
    ENABLE_LANGCHAIN: bool = Field(default=False, alias="QT_ENABLE_LANGCHAIN")

    model_config = SettingsConfigDict(env_prefix="QT_", case_sensitive=False, extra="ignore")

    @property
    def api_key_set(self) -> set[str]:
        if not self.API_KEYS:
            return set()
        return {k.strip() for k in self.API_KEYS.split(",") if k.strip()}


class VersionInfo(BaseModel):
    version: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
