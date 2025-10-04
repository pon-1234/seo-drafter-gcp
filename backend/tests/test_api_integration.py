import pytest
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


class TestAPIIntegration:
    def test_healthcheck(self):
        """Test healthcheck endpoint."""
        response = client.get("/healthz")
        assert response.status_code == 200
        assert "status" in response.json()
        assert response.json()["status"] == "ok"

    def test_create_prompt_version(self):
        """Test creating a prompt version."""
        payload = {
            "prompt_id": "test-prompt",
            "version": "v1.0",
            "templates": {
                "system": "You are a helpful assistant",
                "user": "Write about {keyword}"
            },
            "variables": ["keyword"],
            "description": "Test prompt"
        }

        response = client.post("/api/prompts", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "v1.0"
        assert "templates" in data

    def test_get_prompt_version(self):
        """Test retrieving a prompt version."""
        # First create one
        payload = {
            "prompt_id": "test-prompt-2",
            "version": "v1.0",
            "templates": {"system": "Test", "user": "Test {keyword}"},
            "variables": ["keyword"],
        }
        client.post("/api/prompts", json=payload)

        # Then retrieve it
        response = client.get("/api/prompts/test-prompt-2?version=v1.0")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "v1.0"

    def test_derive_persona(self):
        """Test persona derivation."""
        payload = {
            "primary_keyword": "Python プログラミング",
            "supporting_keywords": ["初心者", "学習"],
        }

        response = client.post("/api/persona/derive", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "persona" in data
        assert "provenance_search_terms" in data

    def test_create_job(self):
        """Test job creation."""
        payload = {
            "primary_keyword": "SEO対策",
            "supporting_keywords": ["コンテンツ", "戦略"],
            "intent": "information",
            "word_count_range": [1000, 2000],
            "prohibited_claims": [],
            "existing_article_ids": []
        }

        response = client.post("/api/jobs", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["status"] in ["pending", "running"]
        assert data["payload"]["primary_keyword"] == "SEO対策"

    def test_get_nonexistent_draft(self):
        """Test getting a non-existent draft returns 404."""
        response = client.get("/api/drafts/nonexistent-id")
        assert response.status_code == 404
