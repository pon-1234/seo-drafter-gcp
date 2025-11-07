from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:  # pragma: no cover - local fallback
    OPENAI_AVAILABLE = False
    OpenAI = None  # type: ignore
    logger.debug("openai package not available")

try:  # pragma: no cover - optional dependency
    from anthropic import Anthropic
    from anthropic.types import Message as AnthropicMessage
    ANTHROPIC_AVAILABLE = True
except ImportError:  # pragma: no cover - local fallback
    Anthropic = None  # type: ignore
    AnthropicMessage = Any  # type: ignore
    ANTHROPIC_AVAILABLE = False
    logger.debug("anthropic package not available")


SUPPORTED_PROVIDERS = {"openai", "anthropic"}


@dataclass
class LLMGenerationResult:
    text: str
    citations: List[Dict[str, str]]


def _clean_proxy_env() -> bool:
    """Remove proxy-related env vars that break SDK clients."""
    proxy_keys = [
        "OPENAI_PROXY",
        "OPENAI_HTTP_PROXY",
        "OPENAI_HTTPS_PROXY",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "http_proxy",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
    ]
    removed = False
    for key in proxy_keys:
        if os.environ.pop(key, None) is not None:
            removed = True
            logger.info("Removed proxy env var: %s", key)
    return removed


def map_messages_to_anthropic(messages: Sequence[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Convert OpenAI-style chat messages into Anthropic system/user blocks.

    Returns:
        system_prompt: Combined system/developer directives.
        anthropic_messages: Messages payload compatible with Anthropic SDK.
    """
    system_sections: List[str] = []
    user_sections: List[str] = []

    for entry in messages:
        role = entry.get("role", "user")
        content = str(entry.get("content", ""))

        if role == "system":
            system_sections.append(content.strip())
        elif role in {"developer", "assistant"}:
            system_sections.append(f"[{role}]\n{content.strip()}")
        else:  # treat everything else as user content
            user_sections.append(content.strip())

    system_prompt = "\n\n".join(section for section in system_sections if section)
    user_payload = "\n\n---\n\n".join(section for section in user_sections if section)

    if not user_payload:
        user_payload = "回答を生成してください。"

    anthropic_messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": user_payload,
                }
            ],
        }
    ]

    return system_prompt, anthropic_messages


class LLMGateway:
    """Provider-agnostic gateway for chat-completion style models."""

    def __init__(
        self,
        *,
        provider: str = "openai",
        model: str = "gpt-5",
        search_enabled: bool = True,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
    ) -> None:
        provider = provider.lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider}")

        self.provider = provider
        self.model = model
        self.search_enabled = search_enabled
        self._openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self._anthropic_api_key = (
            anthropic_api_key
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("CLAUDE_API_KEY")
        )
        self._client = None

        self._initialize_client()

    # ------------------------------------------------------------------ #
    # Client initialisation
    # ------------------------------------------------------------------ #
    def _initialize_client(self) -> None:
        proxy_removed = _clean_proxy_env()

        if self.provider == "openai":
            if not OPENAI_AVAILABLE:
                raise ImportError("openai package is required. Install with: pip install openai")
            if not self._openai_api_key:
                raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY.")
            self._client = OpenAI(api_key=self._openai_api_key)
        elif self.provider == "anthropic":
            if not ANTHROPIC_AVAILABLE:
                raise ImportError("anthropic package is required. Install with: pip install anthropic")
            if not self._anthropic_api_key:
                raise ValueError("Anthropic API key is required. Set ANTHROPIC_API_KEY or CLAUDE_API_KEY.")
            self._client = Anthropic(api_key=self._anthropic_api_key)
        else:  # pragma: no cover - guarded above
            raise ValueError(f"Unsupported provider: {self.provider}")

        if proxy_removed:
            logger.info("Initialized %s client (proxy env cleared)", self.provider)
        else:
            logger.info("Initialized %s client", self.provider)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def generate_with_grounding(
        self,
        prompt: Optional[str] = None,
        *,
        messages: Optional[Sequence[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 1500,
    ) -> Dict[str, Any]:
        """Generate grounded content using the configured provider."""

        if not messages:
            if not prompt:
                raise ValueError("Either prompt or messages must be provided.")
            messages = [
                {
                    "role": "system",
                    "content": (
                        "あなたはSEO記事を執筆する専門のライターです。"
                        "正確で信頼性の高い情報を提供し、必要に応じて出典を明記してください。"
                        "日本語で自然で読みやすい文章を書いてください。"
                    ),
                },
                {"role": "user", "content": prompt},
            ]

        prepared_messages: List[Dict[str, Any]] = []
        for entry in messages:
            role = entry.get("role", "user")
            if role not in {"system", "user", "assistant", "developer", "tool"}:
                role = "system" if role == "developer" else "user"
            prepared_messages.append({"role": role, "content": entry.get("content", "")})

        if self.search_enabled and self.provider == "openai":
            for entry in prepared_messages:
                if entry["role"] == "system":
                    entry["content"] += (
                        "\n実際の最新情報に基づいて回答してください。"
                        "統計データや事実を述べる際は、出典を [Source: URL] 形式で記載してください。"
                    )
                    break

        raw_text = self._dispatch_generate(
            prepared_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        citations = self._extract_citations(raw_text)
        clean_text = self._remove_citation_markers(raw_text)

        logger.info(
            "Generated text using %s/%s (chars=%d citations=%d)",
            self.provider,
            self.model,
            len(clean_text),
            len(citations),
        )

        return {"text": clean_text, "citations": citations}

    # ------------------------------------------------------------------ #
    # Provider-specific dispatch
    # ------------------------------------------------------------------ #
    def _dispatch_generate(
        self,
        messages: Sequence[Dict[str, Any]],
        *,
        temperature: float,
        max_tokens: Optional[int],
    ) -> str:
        OPENAI_TEMPERATURE_LOCKED_MODELS = {"gpt-5", "gpt-5-mini", "o4-mini"}

        if self.provider == "openai":
            assert OPENAI_AVAILABLE and self._client is not None  # for mypy
            payload: Dict[str, Any] = {
                "model": self.model,
                "messages": list(messages),
            }
            allows_temperature = self.model not in OPENAI_TEMPERATURE_LOCKED_MODELS
            if allows_temperature:
                payload["temperature"] = temperature
            else:
                logger.debug(
                    "Model %s enforces default temperature. Requested=%s ignored.",
                    self.model,
                    temperature,
                )
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens

            response = self._client.chat.completions.create(**payload)
            return response.choices[0].message.content or ""

        if self.provider == "anthropic":
            assert ANTHROPIC_AVAILABLE and self._client is not None  # for mypy
            system_prompt, anthropic_messages = map_messages_to_anthropic(messages)
            response: AnthropicMessage = self._client.messages.create(
                model=self.model,
                system=system_prompt or None,
                messages=anthropic_messages,
                temperature=temperature,
                max_tokens=max_tokens or 1500,
            )
            return self._collect_anthropic_text(response)

        raise ValueError(f"Unsupported provider dispatched: {self.provider}")

    def _collect_anthropic_text(self, response: AnthropicMessage) -> str:
        """Flatten Anthropic message content into a string."""
        parts: List[str] = []
        content: Iterable[Any] = getattr(response, "content", []) or []

        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
            else:
                block_type = getattr(block, "type", None)
                if block_type == "text":
                    parts.append(str(getattr(block, "text", "")))

        return "\n".join(part for part in parts if part).strip()

    # ------------------------------------------------------------------ #
    # Text post-processing helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_citations(content: str) -> List[Dict[str, str]]:
        """Extract citation URLs from content."""
        citation_pattern = r'\[(?:Source|出典|参考):?\s*([^\]]+)\]'
        matches = re.findall(citation_pattern, content, re.IGNORECASE)

        citations = []
        for match in matches:
            url = match.strip()
            if url.startswith(("http://", "https://")):
                citations.append({"uri": url, "url": url, "title": url})
        return citations

    @staticmethod
    def _remove_citation_markers(content: str) -> str:
        """Remove citation markers from content while keeping natural text."""
        content = re.sub(r'\[(?:Source|出典|参考):?\s*[^\]]+\]', '', content, flags=re.IGNORECASE)
        content = re.sub(r'\s+', ' ', content)
        return content.strip()
