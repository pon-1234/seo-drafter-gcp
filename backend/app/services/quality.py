from __future__ import annotations

import logging
from typing import Dict, List, Optional

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

        return DraftQualitySignals(
            duplication_score=duplication_score,
            excessive_claims=[c.get("text", "") for c in claims],
            style_violations=style,
            requires_expert_review=requires_expert,
            citations_missing=missing_citations,
        )

    def bundle(
        self,
        draft_id: str,
        paths: Dict[str, str],
        metadata: Dict[str, str],
        draft_content: Dict,
        signed_urls: Optional[Dict[str, str]] = None,
        internal_links: Optional[List[Dict]] = None,
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
            internal_links=links,
        )
