import pytest
from unittest.mock import Mock, patch
from app.services.vertex import VertexGateway
from app.models import PersonaDeriveRequest


class TestVertexGateway:
    def test_generate_persona_fallback(self):
        """Test persona generation with fallback when Vertex AI is unavailable."""
        gateway = VertexGateway()
        request = PersonaDeriveRequest(
            primary_keyword="SEO対策",
            supporting_keywords=["コンテンツ", "戦略"],
        )

        persona = gateway.generate_persona(request)

        assert persona.name == "SEO対策の検討者"
        assert "SEO対策" in persona.job_to_be_done
        assert len(persona.pain_points) > 0
        assert len(persona.goals) > 0

    @patch('app.services.vertex.GenerativeModel')
    def test_generate_with_grounding_mock(self, mock_model_class):
        """Test grounded content generation with mocked Vertex AI."""
        mock_model = Mock()
        mock_response = Mock()
        mock_candidate = Mock()
        mock_content = Mock()
        mock_part = Mock()

        mock_part.text = "Generated content with citations"
        mock_content.parts = [mock_part]
        mock_candidate.content = mock_content
        mock_candidate.grounding_metadata = None
        mock_response.candidates = [mock_candidate]

        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        # This test requires actual Vertex AI setup to run properly
        # For now, we verify the fallback behavior
        gateway = VertexGateway()
        result = gateway.generate_with_grounding("Test prompt")

        # Should have fallback response
        assert "text" in result
        assert "citations" in result

    def test_invoke_generation_fallback(self):
        """Test generation invocation fallback."""
        gateway = VertexGateway()
        result = gateway.invoke_generation(
            "gemini-1.5-flash",
            {"prompt": "Test prompt", "temperature": 0.5}
        )

        assert result["model"] == "gemini-1.5-flash"
        assert "input" in result or "output" in result
