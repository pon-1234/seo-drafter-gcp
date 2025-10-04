from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - optional dependency
    import sys
    import os
    # Add backend to path for shared services
    backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../backend"))
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    from app.services.bigquery import InternalLinkRepository
    from app.services.vertex import VertexGateway
except ImportError:
    InternalLinkRepository = None  # type: ignore
    VertexGateway = None  # type: ignore

from ..core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    job_id: str
    draft_id: str
    project_id: str
    prompt_version: str
    persona: Dict
    intent: str


class DraftGenerationPipeline:
    """Encapsulates the deterministic order of the draft generation steps."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.vertex_gateway = VertexGateway() if VertexGateway else None
        self.link_repository = InternalLinkRepository() if InternalLinkRepository else None

    def estimate_intent(self, payload: Dict) -> str:
        requested_intent = payload.get("intent")
        if requested_intent:
            logger.info("Job %s intent provided: %s", payload["job_id"], requested_intent)
            return requested_intent
        persona = payload.get("persona", {})
        goals = persona.get("goals", [])
        if any("比較" in goal for goal in goals):
            intent = "comparison"
        elif any("購入" in goal for goal in goals):
            intent = "transaction"
        else:
            intent = "information"
        logger.info("Job %s inferred intent: %s", payload["job_id"], intent)
        return intent

    def generate_outline(self, context: PipelineContext, prompt: Dict) -> Dict:
        logger.info("Generating outline for %s using prompt %s", context.job_id, context.prompt_version)
        outline = {
            "title": f"{prompt['primary_keyword']}とは？最新ガイド",
            "h2": [
                {
                    "text": f"{prompt['primary_keyword']}の基本",
                    "purpose": "Know",
                    "estimated_words": 350,
                    "h3": [
                        {"text": "概要", "purpose": "Know", "estimated_words": 150},
                        {"text": "重要ポイント", "purpose": "Know", "estimated_words": 200},
                    ],
                },
                {
                    "text": "比較検討の視点",
                    "purpose": "Compare",
                    "estimated_words": 300,
                    "h3": [
                        {"text": "主要な評価軸", "purpose": "Compare", "estimated_words": 150},
                        {"text": "他サービスとの違い", "purpose": "Compare", "estimated_words": 150},
                    ],
                },
            ],
        }
        return outline

    def generate_draft(self, context: PipelineContext, outline: Dict, citations: List[Dict]) -> Dict:
        logger.info("Generating draft for %s with %d outline sections", context.job_id, len(outline.get('h2', [])))
        sections = []
        all_claims = []

        for h2 in outline.get("h2", []):
            paragraphs = []
            for h3 in h2.get("h3", []):
                # Use Vertex AI with Grounding for content generation
                prompt = self._build_section_prompt(h3["text"], context)
                grounded_result = self._generate_grounded_content(prompt)

                claim_id = f"{context.draft_id}-{h3['text']}"
                paragraphs.append({
                    "heading": h3["text"],
                    "text": grounded_result.get("text", f"{h3['text']} について解説します。"),
                    "citations": [c.get("uri", c.get("url", "")) for c in grounded_result.get("citations", citations[:2])],
                    "claim_id": claim_id,
                })

                all_claims.append({
                    "id": claim_id,
                    "text": grounded_result.get("text", ""),
                    "citations": grounded_result.get("citations", []),
                })

            sections.append({"h2": h2["text"], "paragraphs": paragraphs})

        return {
            "draft": {
                "sections": sections,
                "faq": self._generate_faq(context),
            },
            "claims": all_claims,
        }

    def _build_section_prompt(self, heading: str, context: PipelineContext) -> str:
        """Build a prompt for generating a specific section."""
        persona_name = context.persona.get("name", "読者")
        tone = context.persona.get("tone", "実務的")
        return (
            f"以下の見出しについて、{persona_name}向けに{tone}なトーンで詳しく解説してください。\n"
            f"見出し: {heading}\n"
            f"検索意図: {context.intent}\n"
            f"必ず信頼できる情報源に基づいて記述してください。"
        )

    def _generate_grounded_content(self, prompt: str) -> Dict[str, Any]:
        """Generate content with Google Search Grounding."""
        if not self.vertex_gateway:
            logger.warning("Vertex Gateway not available, using fallback")
            return {"text": prompt[:100] + "...", "citations": []}

        try:
            return self.vertex_gateway.generate_with_grounding(prompt, temperature=0.7)
        except Exception as e:
            logger.error("Grounded generation failed: %s", e)
            return {"text": prompt[:100] + "...", "citations": []}

    def _generate_faq(self, context: PipelineContext) -> List[Dict]:
        """Generate FAQ section using Vertex AI."""
        persona_name = context.persona.get("name", "読者")
        pain_points = context.persona.get("pain_points", [])

        faq_items = []
        for pain in pain_points[:3]:
            prompt = f"{persona_name}が抱える「{pain}」という課題に対する解決策を簡潔に説明してください。"
            result = self._generate_grounded_content(prompt)
            faq_items.append({
                "question": pain,
                "answer": result.get("text", "解決策を提供します。"),
                "citations": result.get("citations", []),
            })

        if not faq_items:
            faq_items.append({
                "question": f"{persona_name}が抱える疑問は？",
                "answer": "想定される疑問に対して根拠付きで回答します。",
                "citations": [],
            })

        return faq_items

    def generate_meta(self, prompt: Dict) -> Dict:
        keyword = prompt["primary_keyword"]
        return {
            "title_options": [f"{keyword} 完全ガイド", f"{keyword} 比較ポイントまとめ"],
            "description_options": [f"{keyword} の最新情報と比較ポイントを詳しく解説", f"{keyword} の選び方と成功事例"],
            "og": {
                "title": f"{keyword} のベストプラクティス",
                "description": f"{keyword} に関するノウハウを網羅",
            },
        }

    def propose_links(self, prompt: Dict, context: PipelineContext) -> List[Dict]:
        """Propose internal links using BigQuery Vector Search."""
        keyword = prompt["primary_keyword"]
        persona_goals = context.persona.get("goals", [])

        if not self.link_repository:
            logger.warning("Link repository not available, using fallback")
            return [{
                "url": f"https://example.com/articles/{keyword}-guide",
                "title": f"{keyword} ガイド",
                "anchor": f"{keyword} と関連するガイド",
                "score": 0.5,
            }]

        try:
            candidates = self.link_repository.search(keyword, persona_goals, limit=5)
            results = []
            for candidate in candidates:
                results.append({
                    "url": candidate["url"],
                    "title": candidate["title"],
                    "anchor": f"{keyword} と関連する {candidate['title']}",
                    "score": candidate.get("score", 0.5),
                    "snippet": candidate.get("snippet", ""),
                })
            logger.info("Proposed %d internal links for keyword: %s", len(results), keyword)
            return results
        except Exception as e:
            logger.error("Link proposal failed: %s", e)
            return []

    def evaluate_quality(self, draft: Dict) -> Dict:
        claims_without_citations = [c for c in draft.get("claims", []) if not c.get("citations")]
        return {
            "similarity": 0.12,
            "claims": claims_without_citations,
            "style_violations": [],
            "is_ymyl": False,
        }

    def bundle_outputs(self, context: PipelineContext, outline: Dict, draft: Dict, meta: Dict, links: List[Dict], quality: Dict) -> Dict:
        return {
            "outline": outline,
            "draft": draft,
            "meta": meta,
            "links": links,
            "quality": quality,
            "metadata": {
                "job_id": context.job_id,
                "draft_id": context.draft_id,
                "prompt_version": context.prompt_version,
            },
        }

    def run(self, payload: Dict) -> Dict:
        logger.info("Starting pipeline for job %s", payload["job_id"])
        draft_id = payload.get("draft_id") or str(payload["job_id"]).replace("-", "")[:12]
        intent = self.estimate_intent(payload)
        context = PipelineContext(
            job_id=payload["job_id"],
            draft_id=draft_id,
            project_id=payload["project_id"],
            prompt_version=payload.get("prompt_version", self.settings.default_prompt_version),
            persona=payload.get("persona", {}),
            intent=intent,
        )
        outline = self.generate_outline(context, payload)
        citations = payload.get("citations", []) or [
            {"url": "https://www.google.com/search?q=" + payload["primary_keyword"]}
        ]
        draft = self.generate_draft(context, outline, citations)
        meta = self.generate_meta(payload)
        links = self.propose_links(payload, context)
        quality = self.evaluate_quality(draft)
        bundle = self.bundle_outputs(context, outline, draft, meta, links, quality)
        logger.info("Completed pipeline for job %s", payload["job_id"])
        return bundle


def handle_pubsub_message(event, _context) -> Dict:
    # Expected to be Pub/Sub triggered Cloud Run job
    data = json.loads(event["data"]) if isinstance(event, dict) and "data" in event else event
    pipeline = DraftGenerationPipeline()
    return pipeline.run(data)
