"""OpenAI API Gateway for content generation with web search grounding."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("openai package not installed")


class OpenAIGateway:
    """Gateway for OpenAI API with search grounding capabilities."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
        search_enabled: bool = True,
    ) -> None:
        """
        Initialize OpenAI Gateway.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model to use (gpt-4o, gpt-4-turbo, gpt-3.5-turbo)
            search_enabled: Whether to enable web search grounding
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.search_enabled = search_enabled

        if not OPENAI_AVAILABLE:
            raise ImportError("openai package is required. Install with: pip install openai")

        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")

        proxy_cleared = self._clear_proxy_env()

        # Simplified initialization to avoid compatibility issues with proxy kwargs
        try:
            self.client = OpenAI(api_key=self.api_key)
            if proxy_cleared:
                logger.info("OpenAI Gateway initialized with model: %s (proxy env cleared)", self.model)
            else:
                logger.info("OpenAI Gateway initialized with model: %s", self.model)
        except Exception as exc:
            logger.exception("Failed to initialize OpenAI client: %s", exc)
            raise

    @staticmethod
    def _clear_proxy_env() -> bool:
        """Remove proxy-related environment variables that break the OpenAI SDK."""
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
                logger.info("Removing proxy env var: %s", key)
                removed = True
        return removed

    def generate_with_grounding(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 1500,
    ) -> Dict[str, Any]:
        """
        Generate content using OpenAI API.

        Args:
            prompt: The generation prompt
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate

        Returns:
            Dict with 'text' and 'citations' keys
        """
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "あなたはSEO記事を執筆する専門のライターです。"
                        "正確で信頼性の高い情報を提供し、必要に応じて出典を明記してください。"
                        "日本語で自然で読みやすい文章を書いてください。"
                    )
                },
                {"role": "user", "content": prompt}
            ]

            # Use web search if enabled and model supports it
            if self.search_enabled and self.model in ["gpt-4o", "gpt-4-turbo"]:
                # For models that support tools, we can enhance with search-like instructions
                # OpenAI's API does not provide built-in web search, so we coax citations via prompting
                # and post-process the response for potential references.
                logger.info("Generating content with search-aware prompt")
                messages[0]["content"] += (
                    "\n実際の最新情報に基づいて回答してください。"
                    "統計データや事実を述べる際は、出典を [Source: URL] 形式で記載してください。"
                )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            content = response.choices[0].message.content or ""

            # Extract citations from content if present
            citations = self._extract_citations(content)

            # Remove citation markers from content for cleaner output
            clean_content = self._remove_citation_markers(content)

            logger.info(
                "Generated %d chars with %d citations",
                len(clean_content),
                len(citations)
            )

            return {
                "text": clean_content,
                "citations": citations,
            }

        except Exception as e:
            logger.error("OpenAI generation failed: %s", e)
            raise

    def _extract_citations(self, content: str) -> List[Dict[str, str]]:
        """Extract citation URLs from content."""
        import re

        # Look for [Source: URL] or similar patterns
        citation_pattern = r'\[(?:Source|出典|参考):?\s*([^\]]+)\]'
        matches = re.findall(citation_pattern, content, re.IGNORECASE)

        citations = []
        for match in matches:
            # Clean up the URL
            url = match.strip()
            if url.startswith(('http://', 'https://')):
                citations.append({
                    "uri": url,
                    "url": url,
                    "title": url,  # Could be enhanced with actual title fetching
                })

        return citations

    def _remove_citation_markers(self, content: str) -> str:
        """Remove citation markers from content while keeping the text natural."""
        import re

        # Remove [Source: URL] style citations
        content = re.sub(r'\[(?:Source|出典|参考):?\s*[^\]]+\]', '', content, flags=re.IGNORECASE)

        # Clean up extra whitespace
        content = re.sub(r'\s+', ' ', content)
        content = content.strip()

        return content

    def generate_persona(
        self,
        industry: str,
        goals: List[str],
        pain_points: List[str],
        tone: str = "実務的",
    ) -> Dict[str, Any]:
        """
        Generate a persona description using OpenAI.

        Args:
            industry: Target industry
            goals: List of persona goals
            pain_points: List of pain points
            tone: Desired tone

        Returns:
            Persona dictionary
        """
        prompt = f"""
以下の情報に基づいて、SEO記事のターゲットペルソナを生成してください。

業界: {industry}
目標: {', '.join(goals)}
課題: {', '.join(pain_points)}
トーン: {tone}

以下の形式でペルソナを出力してください：
- 名前: [典型的な役職名]
- 特徴: [2-3文で特徴を説明]
- 情報ニーズ: [求めている情報の種類]
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "あなたはマーケティングペルソナの専門家です。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500,
            )

            content = response.choices[0].message.content or ""

            return {
                "name": industry + "の検討者",
                "goals": goals,
                "pain_points": pain_points,
                "tone": tone,
                "description": content,
            }

        except Exception as e:
            logger.error("Persona generation failed: %s", e)
            raise
