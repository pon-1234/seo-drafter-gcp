"""BigQuery-backed internal link repository shared by backend and worker services."""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, TYPE_CHECKING

try:  # pragma: no cover - optional dependency
    from google.cloud import bigquery  # type: ignore
except ImportError:  # pragma: no cover - local fallback when bigquery is unavailable
    bigquery = None

if TYPE_CHECKING:  # pragma: no cover - import only for type hints
    from google.cloud.bigquery.table import Row

logger = logging.getLogger(__name__)


def _detect_project_id() -> Optional[str]:
    """Best-effort resolution of the active GCP project id."""
    loaders = []
    try:
        from backend.app.core.config import get_settings as backend_get_settings  # type: ignore

        loaders.append(lambda: backend_get_settings().project_id)
    except Exception:  # pragma: no cover - backend module not importable in worker context
        pass

    try:
        from worker.app.core.config import get_settings as worker_get_settings  # type: ignore

        loaders.append(lambda: worker_get_settings().project_id)
    except Exception:  # pragma: no cover - worker module not importable in backend context
        pass

    for loader in loaders:
        try:
            project_id = loader()
            if project_id:
                return project_id
        except Exception:
            continue

    return os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")


class InternalLinkRepository:
    """Provides internal link candidates by querying BigQuery tables."""

    def __init__(self, project_id: Optional[str] = None, dataset: str = "seo_drafter") -> None:
        self._project_id = project_id or _detect_project_id()
        self._dataset = dataset
        self._client = None

        if not bigquery:
            logger.warning(
                "google-cloud-bigquery not installed; internal link suggestions are disabled"
            )
            return

        if not self._project_id:
            logger.warning("GCP project id is not configured; internal link suggestions are disabled")
            return

        try:
            self._client = bigquery.Client(project=self._project_id)
        except Exception as exc:  # pragma: no cover - network/auth issues
            logger.warning("Failed to initialize BigQuery client: %s", exc)
            self._client = None

    @property
    def is_enabled(self) -> bool:
        return self._client is not None

    def search(self, keyword: str, persona_goals: List[str], limit: int = 5) -> List[Dict]:
        """Return relevant internal link suggestions, ordered by a simple relevance score."""
        if not keyword:
            return []

        goals = [goal.strip() for goal in persona_goals if goal and goal.strip()]

        if not self._client:
            logger.info("Internal link repository disabled; returning no suggestions")
            return []

        try:
            candidates = self._query_articles(keyword, goals, limit)
            if not candidates:
                # Fallback: surface the most recently updated published articles
                candidates = self._query_recent_articles(limit)
            return candidates
        except Exception as exc:  # pragma: no cover - BigQuery runtime failure
            logger.error("Internal link search failed: %s", exc)
            return []

    def _query_articles(self, keyword: str, goals: List[str], limit: int) -> List[Dict]:
        if not self._client or not bigquery:
            return []

        query = f"""
        SELECT
          url,
          title,
          COALESCE(snippet, "") AS snippet,
          updated_at
        FROM `{self._project_id}.{self._dataset}.articles`
        WHERE
          published = TRUE
          AND (
            LOWER(title) LIKE CONCAT('%', LOWER(@keyword), '%')
            OR LOWER(COALESCE(snippet, '')) LIKE CONCAT('%', LOWER(@keyword), '%')
            OR (
              ARRAY_LENGTH(@goals) > 0 AND EXISTS (
                SELECT 1 FROM UNNEST(@goals) AS goal
                WHERE LOWER(COALESCE(snippet, '')) LIKE CONCAT('%', LOWER(goal), '%')
              )
            )
          )
        ORDER BY updated_at DESC
        LIMIT @limit
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("keyword", "STRING", keyword),
                bigquery.ArrayQueryParameter("goals", "STRING", goals),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
            ]
        )

        job = self._client.query(query, job_config=job_config)
        return [
            self._serialize_candidate(row, keyword, goals)
            for row in job
        ]

    def _query_recent_articles(self, limit: int) -> List[Dict]:
        if not self._client or not bigquery:
            return []

        query = f"""
        SELECT
          url,
          title,
          COALESCE(snippet, "") AS snippet,
          updated_at
        FROM `{self._project_id}.{self._dataset}.articles`
        WHERE published = TRUE
        ORDER BY updated_at DESC
        LIMIT @limit
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("limit", "INT64", limit)]
        )

        job = self._client.query(query, job_config=job_config)
        return [
            self._serialize_candidate(row, keyword="", goals=[])
            for row in job
        ]

    @staticmethod
    def _serialize_candidate(row: "Row", keyword: str, goals: List[str]) -> Dict:
        title = row.title or ""
        snippet = row.snippet or ""
        score = InternalLinkRepository._compute_score(title, snippet, keyword, goals)
        return {
            "url": row.url,
            "title": title,
            "snippet": snippet,
            "score": score,
            "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
        }

    @staticmethod
    def _compute_score(title: str, snippet: str, keyword: str, goals: List[str]) -> float:
        base_score = 0.1
        keyword_lower = keyword.lower()
        snippet_lower = snippet.lower()
        title_lower = title.lower()

        if keyword and keyword_lower in title_lower:
            base_score += 0.55
        if keyword and keyword_lower in snippet_lower:
            base_score += 0.2

        for goal in goals:
            goal_lower = goal.lower()
            if goal_lower and goal_lower in snippet_lower:
                base_score += 0.15
                break

        return round(min(base_score, 0.99), 3)

    def store_article_embedding(
        self,
        article_id: str,
        url: str,
        title: str,
        snippet: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """Upsert the provided article metadata into the articles table.

        Embedding storage is currently a no-op; this method focuses on keeping
        the text index fresh so internal link suggestions remain meaningful.
        """

        if not self._client or not bigquery:
            logger.info("BigQuery client unavailable; skipping article indexing")
            return False

        trimmed_snippet = (snippet or "").strip()[:500]

        query = f"""
        MERGE `{self._project_id}.{self._dataset}.articles` AS target
        USING (
          SELECT
            @article_id AS article_id,
            @url AS url,
            @title AS title,
            @snippet AS snippet
        ) AS source
        ON target.article_id = source.article_id
        WHEN MATCHED THEN
          UPDATE SET
            url = source.url,
            title = source.title,
            snippet = source.snippet,
            published = TRUE,
            updated_at = CURRENT_TIMESTAMP()
        WHEN NOT MATCHED THEN
          INSERT (article_id, url, title, snippet, published, updated_at)
          VALUES (source.article_id, source.url, source.title, source.snippet, TRUE, CURRENT_TIMESTAMP())
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("article_id", "STRING", article_id),
                bigquery.ScalarQueryParameter("url", "STRING", url),
                bigquery.ScalarQueryParameter("title", "STRING", title),
                bigquery.ScalarQueryParameter("snippet", "STRING", trimmed_snippet),
            ]
        )

        try:
            self._client.query(query, job_config=job_config).result()
            logger.info("Upserted article metadata for internal linking: %s", article_id)
            return True
        except Exception as exc:  # pragma: no cover - BigQuery runtime failure
            logger.error("Failed to upsert article metadata: %s", exc)
            return False


__all__ = ["InternalLinkRepository"]
