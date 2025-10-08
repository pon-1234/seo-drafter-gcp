from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - optional dependency
    from google.cloud import aiplatform  # type: ignore
    import vertexai  # type: ignore
    from vertexai.generative_models import GenerativeModel, Tool  # type: ignore
    from vertexai.preview import grounding  # type: ignore
except ImportError:  # pragma: no cover - local fallback
    aiplatform = None
    vertexai = None
    GenerativeModel = None
    Tool = None
    grounding = None

from ..core.config import get_settings
from ..models import ArticleType, Persona, PersonaBrief, PersonaDeriveRequest

logger = logging.getLogger(__name__)


class VertexGateway:
    """Facade for Vertex AI model invocation with offline fallback."""

    def __init__(self) -> None:
        self._settings = get_settings()
        if vertexai:
            vertexai.init(project=self._settings.project_id, location="asia-northeast1")

    def generate_persona(self, request: PersonaDeriveRequest) -> Persona:
        prompt = self._build_persona_prompt(request)
        if GenerativeModel:
            model = GenerativeModel(self._settings.vertex_model_flash)
            result = model.generate_content(prompt, generation_config={"temperature": 0.2})
            try:
                data = result.candidates[0].text  # type: ignore[attr-defined]
            except (KeyError, IndexError, AttributeError):
                logger.warning("Vertex response missing text; falling back to heuristic persona")
                data = None
            if data:
                try:
                    payload = Persona.parse_raw(data)
                    return payload
                except Exception:
                    logger.warning("Unable to parse persona JSON; continuing with heuristic fallback")

        brief = request.persona_brief or PersonaBrief(job_role="検討者", needs=[], prohibited_expressions=[])
        inferred_intent = {
            ArticleType.information: "information",
            ArticleType.comparison: "comparison",
            ArticleType.ranking: "comparison",
            ArticleType.closing: "transaction",
        }.get(request.article_type or ArticleType.information, "information")

        return Persona(
            name=f"{brief.job_role}向け{request.primary_keyword}検討者",
            job_to_be_done=request.intended_cta or f"{request.primary_keyword} に関する最適な情報収集",
            pain_points=brief.needs or ["必要な情報が整理されていない", "時間が不足している"],
            goals=[request.intended_cta or "信頼できる情報だけを得たい"],
            reading_level="中級",
            tone="実務的で信頼性が高い",
            search_intent=inferred_intent,
            success_metrics=["CTA達成率", "資料DL数"],
        )

    def invoke_generation(self, model: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if not GenerativeModel:
            logger.info("Vertex AI SDK not available; returning input as echo")
            return {"model": model, "input": input_data, "output": {"echo": True}}

        gen_model = GenerativeModel(model)
        response = gen_model.generate_content(
            [input_data["prompt"]],
            generation_config={
                "temperature": input_data.get("temperature", 0.7),
                "seed": input_data.get("seed", self._settings.seed),
            },
            safety_settings=input_data.get("safety_settings"),
        )
        return {
            "model": model,
            "output": response.candidates[0].content.parts[0].text,  # type: ignore[attr-defined]
        }

    def generate_with_grounding(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        use_google_search: bool = True,
    ) -> Dict[str, Any]:
        """Generate content with Google Search Grounding for citations."""
        if not aiplatform or not GenerativeModel or not grounding:
            logger.warning("Vertex AI Grounding not available; returning mock response")
            return {
                "text": f"Generated response for: {prompt[:50]}...",
                "grounding_metadata": {"web_search_queries": [], "grounding_support": []},
                "citations": [],
            }

        model_name = model or self._settings.vertex_model_pro
        gen_model = GenerativeModel(model_name)

        tools = []
        if use_google_search:
            tools.append(Tool.from_google_search_retrieval(grounding.GoogleSearchRetrieval()))

        try:
            response = gen_model.generate_content(
                prompt,
                tools=tools if tools else None,
                generation_config={
                    "temperature": temperature,
                    "seed": self._settings.seed,
                },
            )

            text = response.candidates[0].content.parts[0].text  # type: ignore[attr-defined]
            grounding_metadata = getattr(response.candidates[0], "grounding_metadata", None)  # type: ignore[attr-defined]

            citations = []
            if grounding_metadata:
                for support in getattr(grounding_metadata, "grounding_support", []):
                    for chunk in getattr(support, "grounding_chunk_indices", []):
                        retrieval_metadata = getattr(grounding_metadata, "retrieval_metadata", None)
                        if retrieval_metadata:
                            for ref in getattr(retrieval_metadata, "web_dynamic_retrieval_score", []):
                                citations.append({
                                    "uri": getattr(ref, "uri", ""),
                                    "title": getattr(ref, "title", ""),
                                })

            return {
                "text": text,
                "grounding_metadata": grounding_metadata,
                "citations": citations,
            }
        except Exception as e:
            logger.error("Grounding generation failed: %s", e)
            return {
                "text": "",
                "grounding_metadata": {},
                "citations": [],
                "error": str(e),
            }

    def _build_persona_prompt(self, request: PersonaDeriveRequest) -> str:
        supporting = ", ".join(request.supporting_keywords) or "なし"
        article_type = request.article_type.value if request.article_type else "未指定"
        cta = request.intended_cta or "未指定"
        brief_section = ""
        if request.persona_brief:
            brief = request.persona_brief
            brief_section = (
                "\n想定読者:\n"
                f"- 職種: {brief.job_role}\n"
                f"- 経験年数: {brief.experience_years or '未指定'}\n"
                f"- ニーズ: {', '.join(brief.needs) or '未指定'}\n"
                f"- 禁則表現: {', '.join(brief.prohibited_expressions) or '特になし'}"
            )
        return (
            "次のキーワードに基づいてSEO記事のペルソナをJSONで返してください。"\
            f"\n主キーワード: {request.primary_keyword}"\
            f"\n補助キーワード: {supporting}"\
            f"\n地域: {request.region or '未指定'}"\
            f"\nデバイス: {request.device or '未指定'}"\
            f"\n記事タイプ: {article_type}"\
            f"\n想定CTA: {cta}"\
            "\n出力フォーマット: "
            "{\"name\": str, \"job_to_be_done\": str, \"pain_points\": [str], "
            "\"goals\": [str], \"reading_level\": str, \"tone\": str, \"search_intent\": str, \"success_metrics\": [str]}"\
            f"{brief_section}"
        )
