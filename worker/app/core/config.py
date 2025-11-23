from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

    project_id: str = Field(default="local-dev", alias="GCP_PROJECT")
    region: str = Field(default="asia-northeast1", alias="GCP_REGION")
    drafts_bucket: str = Field(default="seo-drafter-dev", alias="DRAFTS_BUCKET")
    embedding_model: str = Field(default="text-embedding-004", alias="EMBEDDING_MODEL")
    prompts_bucket: Optional[str] = Field(default=None, alias="PROMPTS_BUCKET")
    default_prompt_version: str = Field(default="v1", alias="DEFAULT_PROMPT_VERSION")
    seed: int = Field(default=42, alias="GENERATION_SEED")

    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5", alias="OPENAI_MODEL")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-4-5", alias="ANTHROPIC_MODEL")
    llm_max_workers: int = Field(default=4, alias="LLM_MAX_WORKERS")
    log_prompts: bool = Field(default=False, alias="LOG_PROMPTS")
    log_prompts_max_chars: int = Field(default=2000, alias="LOG_PROMPTS_MAX_CHARS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
