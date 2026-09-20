from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class ModelOptions(BaseModel):
    """Explicit, reproducible inference settings for an exact provider model ID."""
    model_config = ConfigDict(extra="forbid", strict=True)

    temperature: float | None = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"] | None = None
    max_output_tokens: int = Field(default=4000, ge=512, le=32768)
    provider_order: list[str] | None = None
    provider_ignore: list[str] | None = None
    allow_fallbacks: bool = True


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_model: str = "openai/gpt-6-astra"
    openrouter_review_model: str = "openai/gpt-6-astra"
    openrouter_model_options: dict[str, ModelOptions] = Field(default_factory=lambda: {
        "openai/gpt-6-astra": ModelOptions(reasoning_effort="high", max_output_tokens=8000,
                                         provider_ignore=["openai/flex"]),
    })
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    openrouter_embedding_dimensions: int = 1536
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    data_dir: Path = ROOT / ".runtime"
    corpus_dir: Path = ROOT / "data" / "corpus"
    evaluation_path: Path = ROOT / "data" / "model_evaluation_gold.json"
    frontend_dist: Path = ROOT / "frontend" / "dist"
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "::1"]
    soffice_path: str | None = None
    daily_evaluation: bool = True
    provider_timeout_seconds: float = 120
    operation_timeout_seconds: float = 360
    retrieval_limit: int = 10
    semantic_min_similarity: float = 0.30

    @property
    def configured(self) -> bool:
        return bool(self.openrouter_api_key.get_secret_value().strip())
