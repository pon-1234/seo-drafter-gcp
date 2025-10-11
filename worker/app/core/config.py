from functools import lru_cache
from typing import Optional

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    project_id: str = Field("local-dev", env="GCP_PROJECT")
    region: str = Field("asia-northeast1", env="GCP_REGION")
    drafts_bucket: str = Field("seo-drafter-dev", env="DRAFTS_BUCKET")
    embedding_model: str = Field("text-embedding-004", env="EMBEDDING_MODEL")
    prompts_bucket: Optional[str] = Field(None, env="PROMPTS_BUCKET")
    default_prompt_version: str = Field("v1", env="DEFAULT_PROMPT_VERSION")
    seed: int = Field(42, env="GENERATION_SEED")

    # AI Provider Configuration
    ai_provider: str = Field("openai", env="AI_PROVIDER")  # "openai" or "vertex"
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o", env="OPENAI_MODEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
