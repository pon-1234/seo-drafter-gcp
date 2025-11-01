"""Provider-aware gateway re-exported for worker usage."""

from __future__ import annotations

from typing import Optional

from shared.llm import LLMGateway


class OpenAIGateway(LLMGateway):
    """Compatibility wrapper exposing the legacy constructor signature."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
        search_enabled: bool = True,
        *,
        provider: str = "openai",
        anthropic_api_key: Optional[str] = None,
    ) -> None:
        super().__init__(
            provider=provider,
            model=model,
            search_enabled=search_enabled,
            openai_api_key=api_key,
            anthropic_api_key=anthropic_api_key,
        )


__all__ = ["OpenAIGateway"]
