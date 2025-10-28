from datetime import datetime, timezone

from shared.internal_links import InternalLinkRepository


class _DummyRow:
    def __init__(self, url: str, title: str, snippet: str) -> None:
        self.url = url
        self.title = title
        self.snippet = snippet
        self.updated_at = datetime.now(tz=timezone.utc)


class _DummyJob:
    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)


class _DummyClient:
    def __init__(self, rows):
        self._rows = rows

    def query(self, _query, job_config=None):  # noqa: ARG002
        return _DummyJob(self._rows)


class TestInternalLinkRepository:
    def test_search_returns_scored_results(self):
        repo = InternalLinkRepository(project_id="seo-drafter-gcp")
        dummy_rows = [
            _DummyRow(
                url="https://example.com/marketing-automation",
                title="マーケティングオートメーションとは",
                snippet="マーケティングの自動化でリード育成を加速する方法を解説します。",
            )
        ]
        repo._client = _DummyClient(dummy_rows)  # type: ignore[attr-defined]

        results = repo.search("マーケティング", ["リード育成"], limit=5)

        assert isinstance(results, list)
        assert results[0]["url"].startswith("https://example.com")
        assert results[0]["score"] >= 0.1

    def test_search_returns_empty_when_disabled(self):
        repo = InternalLinkRepository(project_id=None)
        repo._client = None  # type: ignore[attr-defined]

        results = repo.search("SEO対策", [], limit=3)
        assert results == []

    def test_store_article_embedding_without_client(self):
        repo = InternalLinkRepository(project_id=None)
        repo._client = None  # type: ignore[attr-defined]

        success = repo.store_article_embedding(
            article_id="test-123",
            url="https://example.com/test",
            title="Test Article",
            snippet="Test snippet",
            content="Full article content",
            metadata={"category": "seo"},
        )

        assert success is False
