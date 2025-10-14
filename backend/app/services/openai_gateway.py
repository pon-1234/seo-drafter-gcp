"""OpenAI API Gateway for content generation with web search grounding."""

from __future__ import annotations

import logging
import os
import json
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("openai package not installed")

from ..models import ArticleType, Persona, PersonaBrief, PersonaDeriveRequest


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
        prompt: Optional[str] = None,
        *,
        messages: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 1500,
    ) -> Dict[str, Any]:
        """
        Generate content using OpenAI API.

        Args:
            prompt: The generation prompt
            messages: Optional list of chat messages for layered prompting
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate

        Returns:
            Dict with 'text' and 'citations' keys
        """
        try:
            if messages:
                message_payload: List[Dict[str, Any]] = []
                for entry in messages:
                    role = entry.get("role", "user")
                    if role not in {"system", "user", "assistant", "tool"}:
                        role = "system" if role == "developer" else "user"
                    message_payload.append({"role": role, "content": entry.get("content", "")})
            else:
                if not prompt:
                    raise ValueError("Either prompt or messages must be provided.")
                message_payload = [
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
                for entry in message_payload:
                    if entry["role"] == "system":
                        entry["content"] += (
                            "\n実際の最新情報に基づいて回答してください。"
                            "統計データや事実を述べる際は、出典を [Source: URL] 形式で記載してください。"
                        )
                        break

            response = self.client.chat.completions.create(
                model=self.model,
                messages=message_payload,
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

    def generate_persona(self, request: "PersonaDeriveRequest") -> "Persona":  # type: ignore[name-defined]
        """Generate a Persona model from a PersonaDeriveRequest."""
        if not isinstance(request, PersonaDeriveRequest):
            raise TypeError("generate_persona expects PersonaDeriveRequest")

        brief: PersonaBrief = request.persona_brief or PersonaBrief(
            job_role="検討者", needs=[], prohibited_expressions=[]
        )

        # Build a structured JSON prompt for OpenAI.
        supporting = ", ".join(request.supporting_keywords) or "特になし"
        prohibited = ", ".join(brief.prohibited_expressions) or "特になし"
        needs = ", ".join(brief.needs) or "明確な情報整理と意思決定のための根拠"
        tone = "実務的で信頼性を重視"
        intent_map = {
            ArticleType.information: "information",
            ArticleType.comparison: "comparison",
            ArticleType.ranking: "comparison",
            ArticleType.closing: "transaction",
        }
        search_intent = intent_map.get(request.article_type or ArticleType.information, "information")

        prompt = f"""
以下の条件で B2B マーケティング向けのペルソナ情報を JSON1行で出力してください。

- 主キーワード: {request.primary_keyword}
- 補助キーワード: {supporting}
- 読者の職種: {brief.job_role}
- 読者の課題/ニーズ: {needs}
- 想定CTA: {request.intended_cta or '意思決定を促す行動'}
- 禁則表現: {prohibited}
- 想定トーン: {tone}

出力フォーマット (JSON):
{{
  "name": string,
  "job_to_be_done": string,
  "pain_points": [string],
  "goals": [string],
  "reading_level": string,
  "tone": string,
  "search_intent": string,
  "success_metrics": [string]
}}
"""

        persona_payload: Optional[Dict[str, Any]] = None
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "あなたはB2Bマーケティングのペルソナ設計の専門家です。JSONのみで回答してください。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            content = response.choices[0].message.content or ""
            persona_payload = self._extract_persona_json(content)
        except Exception as exc:
            logger.exception("Persona generation request failed: %s", exc)

        return self._build_persona_from_payload(
            request=request,
            brief=brief,
            inferred_intent=search_intent,
            payload=persona_payload,
        )

    def _extract_persona_json(self, content: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, flags=re.S)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    logger.debug("Failed to parse persona JSON from extracted chunk")
        logger.debug("Unable to parse persona JSON from OpenAI response")
        return None

    def _build_persona_from_payload(
        self,
        *,
        request: "PersonaDeriveRequest",
        brief: "PersonaBrief",
        inferred_intent: str,
        payload: Optional[Dict[str, Any]],
    ) -> "Persona":  # type: ignore[name-defined]
        from ..models import Persona

        default_name = f"{brief.job_role}向け{request.primary_keyword}検討者"
        default_goals = [
            request.intended_cta or "信頼できる情報を基に次のアクションを決めたい",
            f"{request.primary_keyword}の要点を短時間で理解したい",
        ]
        default_pain = brief.needs or ["必要な情報が散在している", "意思決定の根拠が不足している"]
        default_success = ["CTA達成率", "資料請求数"]

        if payload:
            name = (payload.get("name") or default_name).strip()
            job_to_be_done = (payload.get("job_to_be_done") or request.intended_cta or default_goals[0]).strip()
            goals = self._ensure_list(payload.get("goals"), default_goals)
            pain_points = self._ensure_list(payload.get("pain_points"), default_pain)
            reading_level = (payload.get("reading_level") or "中級").strip()
            tone = (payload.get("tone") or "実務的").strip()
            search_intent = self._coerce_intent(payload.get("search_intent"), inferred_intent)
            success_metrics = self._ensure_list(payload.get("success_metrics"), default_success)
        else:
            name = default_name
            job_to_be_done = request.intended_cta or default_goals[0]
            goals = default_goals
            pain_points = default_pain
            reading_level = "中級"
            tone = "実務的"
            search_intent = inferred_intent
            success_metrics = default_success

        persona = Persona(
            name=name,
            job_to_be_done=job_to_be_done,
            pain_points=pain_points,
            goals=goals,
            reading_level=reading_level,
            tone=tone,
            search_intent=search_intent,
            success_metrics=success_metrics,
        )
        return persona

    @staticmethod
    def _ensure_list(value: Any, default: List[str]) -> List[str]:
        if isinstance(value, list) and value:
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return default

    @staticmethod
    def _coerce_intent(value: Any, fallback: str) -> str:
        if isinstance(value, str):
            normalized = value.strip().lower()
            mapping = {
                'info': 'information',
                'informational': 'information',
                'information': 'information',
                'compare': 'comparison',
                'comparison': 'comparison',
                'transactional': 'transaction',
                'transaction': 'transaction',
            }
            if normalized in mapping:
                return mapping[normalized]
        return fallback
