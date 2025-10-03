from __future__ import annotations

import logging
from typing import Dict, List

try:  # pragma: no cover - optional dependency
    from google.cloud import bigquery  # type: ignore
except ImportError:  # pragma: no cover - local fallback
    bigquery = None

from ..core.config import get_settings

logger = logging.getLogger(__name__)


class InternalLinkRepository:
    """Queries BigQuery vector search for internal link recommendations."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = bigquery.Client(project=self._settings.project_id) if bigquery else None

    def search(self, keyword: str, persona_goals: List[str], limit: int = 5) -> List[Dict]:
        if not self._client:
            logger.info("BigQuery client unavailable; returning stub results")
            return [
                {
                    "url": f"https://example.com/articles/{keyword}-guide",
                    "title": f"{keyword} ガイド",
                    "score": 0.78,
                }
            ]

        # Placeholder query; to be replaced with vector search once dataset is ready.
        query = f"""
        SELECT url, title, 0.0 AS score
        FROM `{self._settings.project_id}.dataset.articles`
        WHERE CONTAINS_SUBSTR(summary, @keyword)
        LIMIT @limit
        """
        job = self._client.query(query, job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("keyword", "STRING", keyword),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
            ]
        ))
        results = []
        for row in job:
            results.append({"url": row.url, "title": row.title, "score": row.score})
        return results
