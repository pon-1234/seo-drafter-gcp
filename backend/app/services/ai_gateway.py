"""Provider-aware AI gateway with persona generation helpers."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from shared.llm import LLMGateway

from ..models import ArticleType, Persona, PersonaBrief, PersonaDeriveRequest

logger = logging.getLogger(__name__)


class AIGateway(LLMGateway):
    """Extends the shared LLM gateway with persona generation utilities."""

    def __init__(
        self,
        *,
        provider: str = "openai",
        model: str = "gpt-4o",
        search_enabled: bool = True,
        api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        claude_api_key: Optional[str] = None,
    ) -> None:
        resolved_openai_key = openai_api_key or (api_key if provider.lower() == "openai" else None)
        resolved_anthropic_key = (
            anthropic_api_key
            or claude_api_key
            or (api_key if provider.lower() == "anthropic" else None)
        )

        super().__init__(
            provider=provider,
            model=model,
            search_enabled=search_enabled,
            openai_api_key=resolved_openai_key,
            anthropic_api_key=resolved_anthropic_key,
        )

    # ------------------------------------------------------------------ #
    # Persona generation
    # ------------------------------------------------------------------ #
    def generate_persona(self, request: PersonaDeriveRequest) -> Persona:
        if not isinstance(request, PersonaDeriveRequest):
            raise TypeError("generate_persona expects PersonaDeriveRequest")

        brief: PersonaBrief = request.persona_brief or PersonaBrief(
            job_role="検討者", needs=[], prohibited_expressions=[]
        )

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
            content = self._complete_persona_prompt(prompt)
            if content:
                persona_payload = self._extract_persona_json(content)
        except Exception as exc:  # pragma: no cover - network errors hard to simulate
            logger.exception("Persona generation request failed: %s", exc)

        return self._build_persona_from_payload(
            request=request,
            brief=brief,
            inferred_intent=search_intent,
            payload=persona_payload,
        )

    def _complete_persona_prompt(self, prompt: str) -> str:
        if self.provider == "openai":
            response = self._client.chat.completions.create(  # type: ignore[operator]
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "あなたはB2Bマーケティングのペルソナ設計の専門家です。JSONのみで回答してください。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            return response.choices[0].message.content or ""

        if self.provider == "anthropic":
            response = self._client.messages.create(  # type: ignore[union-attr]
                model=self.model,
                system="あなたはB2Bマーケティングのペルソナ設計の専門家です。JSONのみで回答してください。",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt,
                            }
                        ],
                    }
                ],
                temperature=0.3,
                max_tokens=500,
            )
            return self._collect_anthropic_text(response)

        raise ValueError(f"Unsupported provider for persona generation: {self.provider}")

    @staticmethod
    def _extract_persona_json(content: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, flags=re.S)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    logger.debug("Failed to parse persona JSON from extracted chunk")
        logger.debug("Unable to parse persona JSON from response")
        return None

    def _build_persona_from_payload(
        self,
        *,
        request: PersonaDeriveRequest,
        brief: PersonaBrief,
        inferred_intent: str,
        payload: Optional[Dict[str, Any]],
    ) -> Persona:
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

        return Persona(
            name=name,
            job_to_be_done=job_to_be_done,
            goals=goals,
            pain_points=pain_points,
            reading_level=reading_level,
            tone=tone,
            search_intent=search_intent,
            success_metrics=success_metrics,
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _ensure_list(value: Any, default: Any) -> Any:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [item.strip() for item in re.split(r"[,、，\n]+", value) if item.strip()]
        return list(default)

    @staticmethod
    def _coerce_intent(value: Any, fallback: str) -> str:
        if isinstance(value, str):
            value_lower = value.strip().lower()
            if value_lower in {"information", "comparison", "transaction"}:
                return value_lower
        return fallback
