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
            "templates": [
                {"layer": "system", "content": "You are a helpful assistant."},
                {"layer": "user", "content": "Write about {keyword}."}
            ],
            "variables": {"keyword": "Python"},
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
            "templates": [
                {"layer": "system", "content": "Test"},
                {"layer": "user", "content": "Test {keyword}"}
            ],
            "variables": {"keyword": "value"},
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
            "article_type": "information",
            "intended_cta": "資料DL",
            "persona_brief": {
                "job_role": "マーケティング担当",
                "experience_years": "1-3年",
                "needs": ["効率的な学習方法"],
                "prohibited_expressions": ["初心者でも簡単"]
            }
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
            "word_count_range": "2000-2500",
            "prohibited_claims": ["No medical claims"],
            "existing_article_ids": [],
            "article_type": "comparison",
            "intended_cta": "問い合わせ",
            "output_format": "html",
            "quality_rubric": "standard",
            "reference_urls": ["https://example.com"],
            "notation_guidelines": "英数字は半角統一",
            "heading_directive": {
                "mode": "manual",
                "headings": ["リード", "要点", "CTA"]
            },
            "persona_brief": {
                "job_role": "マーケティングマネージャー",
                "experience_years": "3-5年",
                "needs": ["社内説得用の根拠"],
                "prohibited_expressions": ["完全無料"]
            }
        }

        response = client.post("/api/jobs", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["status"] in ["pending", "running"]
        assert data["payload"]["primary_keyword"] == "SEO対策"
        assert data["payload"]["article_type"] == "comparison"
        assert data["payload"]["heading_directive"]["mode"] == "manual"

    def test_get_nonexistent_draft(self):
        """Test getting a non-existent draft returns 404."""
        response = client.get("/api/drafts/nonexistent-id")
        assert response.status_code == 404
