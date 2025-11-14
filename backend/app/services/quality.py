from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..models import DraftBundle, DraftQualitySignals, InternalLink

logger = logging.getLogger(__name__)


class QualityEngine:
    """Evaluates draft quality signals and annotations."""

    def evaluate(self, draft_content: Dict) -> DraftQualitySignals:
        duplication_score = float(draft_content.get("similarity", 0.1))
        claims = [c for c in draft_content.get("claims", []) if not c.get("citations")]
        style = draft_content.get("style_violations", [])
        requires_expert = draft_content.get("is_ymyl", False)
        missing_citations = [c["id"] for c in claims]
        citation_count = int(draft_content.get("citation_count", 0))
        numeric_facts = int(draft_content.get("numeric_facts", 0))
        banned_hits = [str(item) for item in draft_content.get("ng_phrases", [])]
        abstract_hits = [str(item) for item in draft_content.get("abstract_phrases", [])]

        rubric_payload = draft_content.get("rubric", {}) if isinstance(draft_content, dict) else {}
        rubric_summary = draft_content.get("rubric_summary") if isinstance(draft_content, dict) else None
        rubric_scores = {}
        if isinstance(rubric_payload, dict):
            rubric_scores = {key: str(value) for key, value in rubric_payload.items() if key != "summary"}
            rubric_summary = rubric_summary or rubric_payload.get("summary")

        return DraftQualitySignals(
            duplication_score=duplication_score,
            excessive_claims=[c.get("text", "") for c in claims],
            style_violations=style,
            requires_expert_review=requires_expert,
            citations_missing=missing_citations,
            rubric_scores=rubric_scores,
            rubric_summary=rubric_summary,
            citation_count=citation_count,
            numeric_facts=numeric_facts,
            banned_phrase_hits=banned_hits,
            abstract_phrase_hits=abstract_hits,
        )

    def bundle(
        self,
        draft_id: str,
        paths: Dict[str, str],
        metadata: Dict[str, str],
        draft_content: Dict,
        meta: Optional[Dict[str, Any]] = None,
        signed_urls: Optional[Dict[str, str]] = None,
        internal_links: Optional[List[Dict]] = None,
        draft_text: Optional[str] = None,
    ) -> DraftBundle:
        quality = self.evaluate(draft_content)

        # Convert internal links dict to InternalLink models
        links = None
        if internal_links:
            links = [
                InternalLink(
                    url=link["url"],
                    title=link["title"],
                    anchor=link["anchor"],
                    score=link["score"],
                    snippet=link.get("snippet"),
                )
                for link in internal_links
            ]

        return DraftBundle(
            draft_id=draft_id,
            gcs_paths=paths,
            signed_urls=signed_urls,
            quality=quality,
            metadata=metadata,
            meta=meta,
            internal_links=links,
            draft_content=draft_text,
        )
