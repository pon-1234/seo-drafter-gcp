from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Dict, List

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
        for h2 in outline.get("h2", []):
            paragraphs = []
            for h3 in h2.get("h3", []):
                paragraphs.append(
                    {
                        "heading": h3["text"],
                        "text": f"{h3['text']} について解説します。{context.persona.get('name', '読者')}向けに最適化。",
                        "citations": [c["url"] for c in citations[:2]],
                        "claim_id": f"{context.draft_id}-{h3['text']}",
                    }
                )
            sections.append({"h2": h2["text"], "paragraphs": paragraphs})

        return {
            "draft": {
                "sections": sections,
                "faq": [
                    {
                        "question": f"{context.persona.get('name', '読者')}が抱える疑問は？",
                        "answer": "想定される疑問に対して根拠付きで回答します。",
                    }
                ],
            },
            "claims": [
                {"id": p["claim_id"], "text": p["text"], "citations": p.get("citations", [])}
                for section in sections
                for p in section["paragraphs"]
            ],
        }

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

    def propose_links(self, prompt: Dict, embeddings: List[Dict]) -> List[Dict]:
        keyword = prompt["primary_keyword"]
        results = []
        for candidate in embeddings[:3]:
            results.append(
                {
                    "url": candidate["url"],
                    "anchor": f"{keyword} と関連する {candidate['title']}",
                    "score": candidate["score"],
                }
            )
        return results

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
        links = self.propose_links(payload, payload.get("link_candidates", []))
        quality = self.evaluate_quality(draft)
        bundle = self.bundle_outputs(context, outline, draft, meta, links, quality)
        logger.info("Completed pipeline for job %s", payload["job_id"])
        return bundle


def handle_pubsub_message(event, _context) -> Dict:
    # Expected to be Pub/Sub triggered Cloud Run job
    data = json.loads(event["data"]) if isinstance(event, dict) and "data" in event else event
    pipeline = DraftGenerationPipeline()
    return pipeline.run(data)
