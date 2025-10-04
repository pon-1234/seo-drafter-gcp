import pytest
from app.services.bigquery import InternalLinkRepository


class TestInternalLinkRepository:
    def test_search_fallback(self):
        """Test internal link search with fallback when BigQuery is unavailable."""
        repo = InternalLinkRepository()
        results = repo.search("SEO対策", ["検索順位向上", "コンテンツ最適化"], limit=5)

        assert len(results) > 0
        assert "url" in results[0]
        assert "title" in results[0]
        assert "score" in results[0]

    def test_store_article_embedding_fallback(self):
        """Test article embedding storage fallback."""
        repo = InternalLinkRepository()
        success = repo.store_article_embedding(
            article_id="test-123",
            url="https://example.com/test",
            title="Test Article",
            snippet="Test snippet",
            content="Full article content",
            metadata={"category": "seo"}
        )

        # Should return False when BigQuery is unavailable
        assert success is False
