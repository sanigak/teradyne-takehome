from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_model: str = "openai/gpt-4.1-mini"
    openrouter_review_model: str = "openai/gpt-4.1"
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    openrouter_embedding_dimensions: int = 1536
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    data_dir: Path = ROOT / ".runtime"
    corpus_dir: Path = ROOT / "data" / "corpus"
    evaluation_path: Path = ROOT / "data" / "evaluation.json"
    frontend_dist: Path = ROOT / "frontend" / "dist"
    soffice_path: str | None = None
    daily_evaluation: bool = True
    provider_timeout_seconds: float = 40
    operation_timeout_seconds: float = 120
    retrieval_limit: int = 10
    semantic_min_similarity: float = 0.30

    @property
    def configured(self) -> bool:
        return bool(self.openrouter_api_key.get_secret_value().strip())
