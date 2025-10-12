from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

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
                    "snippet": f"{keyword}に関する詳細なガイドです。",
                }
            ]

        # Use Vector Search to find semantically similar articles
        try:
            results = self._vector_search(keyword, persona_goals, limit)
            if results:
                return results
        except Exception as e:
            logger.warning("Vector search failed, falling back to text search: %s", e)

        # Fallback to text-based search
        return self._text_search(keyword, limit)

    def _vector_search(self, keyword: str, persona_goals: List[str], limit: int) -> List[Dict]:
        """Perform vector similarity search using stored embeddings."""
        if not self._client:
            return []

        # For now, use text-based search since vector search is not yet implemented
        # TODO: Implement a real vector search backend when available
        logger.info("Vector search not yet configured, using text search fallback")
        return []

    def _text_search(self, keyword: str, limit: int) -> List[Dict]:
        """Fallback text-based search."""
        query = f"""
        SELECT
          url,
          title,
          snippet,
          0.5 AS score
        FROM `{self._settings.project_id}.seo_drafter.articles`
        WHERE
          published = true
          AND (
            LOWER(title) LIKE CONCAT('%', LOWER(@keyword), '%')
            OR LOWER(snippet) LIKE CONCAT('%', LOWER(@keyword), '%')
          )
        ORDER BY updated_at DESC
        LIMIT @limit
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("keyword", "STRING", keyword),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
            ]
        )

        try:
            job = self._client.query(query, job_config=job_config)
            results = []
            for row in job:
                results.append({
                    "url": row.url,
                    "title": row.title,
                    "snippet": row.snippet if hasattr(row, "snippet") else "",
                    "score": float(row.score),
                })
            return results
        except Exception as e:
            logger.error("Text search query failed: %s", e)
            return []

    def store_article_embedding(
        self,
        article_id: str,
        url: str,
        title: str,
        snippet: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Store article with its embedding for future vector search."""
        if not self._client:
            logger.warning("BigQuery client unavailable; skipping embedding storage")
            return False

        # Generate embeddings using a BigQuery ML remote model
        # This would typically be done in a batch job
        insert_query = f"""
        INSERT INTO `{self._settings.project_id}.seo_drafter.article_embeddings`
        (article_id, url, title, snippet, content, metadata, embedding, published, created_at, updated_at)
        SELECT
          @article_id,
          @url,
          @title,
          @snippet,
          @content,
          @metadata,
          ML.GENERATE_EMBEDDING(
            MODEL `{self._settings.project_id}.seo_drafter.embedding_model`,
            (SELECT @content AS content)
          ).embeddings,
          true,
          CURRENT_TIMESTAMP(),
          CURRENT_TIMESTAMP()
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("article_id", "STRING", article_id),
                bigquery.ScalarQueryParameter("url", "STRING", url),
                bigquery.ScalarQueryParameter("title", "STRING", title),
                bigquery.ScalarQueryParameter("snippet", "STRING", snippet),
                bigquery.ScalarQueryParameter("content", "STRING", content),
                bigquery.ScalarQueryParameter("metadata", "JSON", metadata or {}),
            ]
        )

        try:
            self._client.query(insert_query, job_config=job_config).result()
            logger.info("Stored embedding for article: %s", article_id)
            return True
        except Exception as e:
            logger.error("Failed to store article embedding: %s", e)
            return False
