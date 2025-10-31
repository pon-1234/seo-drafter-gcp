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
    drafts_bucket: str = Field(default="seo-drafter-dev", alias="DRAFTS_BUCKET")
    workflow_name: str = Field(default="draft-generation", alias="WORKFLOW_NAME")
    workflow_region: str = Field(default="asia-northeast1", alias="WORKFLOW_REGION")
    firestore_namespace: Optional[str] = Field(default=None, alias="FIRESTORE_NAMESPACE")
    default_prompt_version: str = Field(default="v1", alias="DEFAULT_PROMPT_VERSION")
    seed: int = Field(default=42, alias="GENERATION_SEED")

    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")
    line_channel_access_token: Optional[str] = Field(default=None, alias="LINE_CHANNEL_ACCESS_TOKEN")
    line_api_base_url: str = Field(default="https://api.line.me/v2/bot", alias="LINE_API_BASE_URL")
    line_default_target: Optional[str] = Field(default=None, alias="LINE_DEFAULT_TARGET")


@lru_cache
def get_settings() -> Settings:
    return Settings()
